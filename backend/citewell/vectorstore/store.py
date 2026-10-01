"""
Vector store for Citewell, backed by FAISS.

FAISS gives free, fully local, exact nearest-neighbour search. Embeddings are
L2-normalised (see embedder.py), so inner product IS cosine similarity and
`IndexFlatIP` is exact with zero approximation error. At this corpus size an
approximate index would be solving a problem the project does not have.

FAISS only stores vectors, so the chunk text and metadata behind each vector
are kept in a parallel list and persisted next to the index.

PERSISTENCE FORMAT (changed from earlier versions, for security):
chunks are saved as JSON, not pickle. Loading a pickle executes arbitrary code,
so a tampered index file in a shared or deployed environment would be a
remote-code-execution risk. JSON cannot do that. Files are written atomically
(temp file, then replace) so an interrupted save never leaves a half-written
index, and the manifest records the embedding model so a model change is
detected instead of silently returning bad results.
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

from citewell import config
from citewell.chunking.chunker import Chunk

logger = logging.getLogger(__name__)

FORMAT_VERSION = 2
INDEX_FILE = "index.faiss"
CHUNKS_FILE = "chunks.json"
MANIFEST_FILE = "manifest.json"
LEGACY_CHUNKS_FILE = "chunks.pkl"


class VectorStoreError(RuntimeError):
    """The saved index exists but is inconsistent or unreadable."""


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class VectorStore:
    """A FAISS IndexFlatIP index plus its chunk metadata, with save/load."""

    def __init__(self, embedding_dim: int, embedding_model: Optional[str] = None):
        self.embedding_dim = embedding_dim
        self.embedding_model = embedding_model
        self.index = faiss.IndexFlatIP(embedding_dim)
        self.chunks: List[Chunk] = []  # parallel array: chunks[i] <-> index vector i

    def add(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """
        Add chunks and their embeddings. `embeddings` must be shaped
        (len(chunks), embedding_dim) and already L2-normalised.
        """
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(f"Mismatch: {len(chunks)} chunks but {embeddings.shape[0]} embeddings.")
        if embeddings.ndim != 2 or embeddings.shape[1] != self.embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: index expects {self.embedding_dim}, "
                f"got {embeddings.shape[1] if embeddings.ndim == 2 else embeddings.shape}."
            )

        embeddings = np.ascontiguousarray(embeddings.astype("float32"))
        self.index.add(embeddings)
        self.chunks.extend(chunks)

    def search(self, query_embedding: np.ndarray, top_k: int = None) -> List[Tuple[Chunk, float]]:
        """Return (Chunk, cosine similarity) pairs, best first."""
        top_k = top_k or config.TOP_K

        if self.index.ntotal == 0:
            return []

        query_embedding = np.ascontiguousarray(query_embedding.reshape(1, -1).astype("float32"))
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue  # FAISS pads with -1 when fewer than k results exist
            results.append((self.chunks[idx], float(score)))
        return results

    def save(self, directory: str | Path = None) -> None:
        """
        Persist the index, chunks and a human-readable manifest.

        The index and chunk files are replaced one at a time, and the manifest
        last. `load()` cross-checks the counts, so an interrupted save is
        detected as corruption and the index is rebuilt rather than trusted.
        """
        directory = Path(directory or config.VECTORSTORE_DIR)
        directory.mkdir(parents=True, exist_ok=True)

        index_tmp = directory / (INDEX_FILE + ".tmp")
        faiss.write_index(self.index, str(index_tmp))
        os.replace(index_tmp, directory / INDEX_FILE)

        _atomic_write_text(
            directory / CHUNKS_FILE,
            json.dumps([asdict(c) for c in self.chunks], ensure_ascii=False),
        )

        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_dim": self.embedding_dim,
            "embedding_model": str(self.embedding_model) if self.embedding_model else None,
            "num_chunks": len(self.chunks),
            "sources": sorted({c.source for c in self.chunks}),
        }
        _atomic_write_text(directory / MANIFEST_FILE, json.dumps(manifest, indent=2))

    @classmethod
    def load(cls, directory: str | Path = None) -> "VectorStore":
        """Load a saved store. Raises FileNotFoundError if none exists (or only a legacy one)."""
        directory = Path(directory or config.VECTORSTORE_DIR)
        index_path = directory / INDEX_FILE
        chunks_path = directory / CHUNKS_FILE

        if not index_path.exists() or not chunks_path.exists():
            if (directory / LEGACY_CHUNKS_FILE).exists():
                raise FileNotFoundError(
                    f"The index at {directory} uses an older, unsafe pickle format that is no "
                    f"longer loaded. Rebuild it to continue."
                )
            raise FileNotFoundError(
                f"No saved vector store found at {directory}. Run the ingestion pipeline first to build one."
            )

        try:
            index = faiss.read_index(str(index_path))
            raw_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
            chunks = [Chunk(**item) for item in raw_chunks]
        except Exception as exc:
            raise VectorStoreError(f"The saved index at {directory} could not be read.") from exc

        if index.ntotal != len(chunks):
            raise VectorStoreError(
                f"The saved index at {directory} is inconsistent "
                f"({index.ntotal} vectors but {len(chunks)} chunks)."
            )

        model = None
        manifest_path = directory / MANIFEST_FILE
        if manifest_path.exists():
            try:
                model = json.loads(manifest_path.read_text(encoding="utf-8")).get("embedding_model")
            except Exception:
                logger.warning("Ignoring unreadable manifest at %s", manifest_path)

        store = cls(embedding_dim=index.d, embedding_model=model)
        store.index = index
        store.chunks = chunks
        return store
