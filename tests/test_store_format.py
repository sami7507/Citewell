"""Tests for the JSON (non-pickle) vector store format and its integrity checks."""

import json

import numpy as np
import pytest

from citewell.chunking.chunker import Chunk
from citewell.vectorstore.store import VectorStore, VectorStoreError


def _store(n=4, dim=8, model="test-model"):
    rng = np.random.default_rng(1)
    chunks = [
        Chunk(text=f"chunk {i}", source="a.pdf", page_number=i + 1, chunk_id=f"c{i}",
              chunk_strategy="test", metadata={"clause_number": str(i), "table_heading": None})
        for i in range(n)
    ]
    vectors = rng.standard_normal((n, dim)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    store = VectorStore(embedding_dim=dim, embedding_model=model)
    store.add(chunks, vectors)
    return store, vectors


def test_save_writes_json_and_never_pickle(tmp_path):
    store, _ = _store()
    store.save(tmp_path)

    assert (tmp_path / "chunks.json").exists()
    assert not (tmp_path / "chunks.pkl").exists()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["embedding_model"] == "test-model"
    assert manifest["num_chunks"] == 4


def test_round_trip_preserves_chunks_metadata_and_model(tmp_path):
    store, vectors = _store()
    store.save(tmp_path)
    loaded = VectorStore.load(tmp_path)

    assert loaded.embedding_model == "test-model"
    assert loaded.chunks[2].metadata == {"clause_number": "2", "table_heading": None}
    assert loaded.search(vectors[1], top_k=1)[0][0].chunk_id == "c1"


def test_legacy_pickle_index_is_refused_with_a_clear_message(tmp_path):
    (tmp_path / "index.faiss").write_bytes(b"x")
    (tmp_path / "chunks.pkl").write_bytes(b"x")

    with pytest.raises(FileNotFoundError, match="older, unsafe pickle format"):
        VectorStore.load(tmp_path)


def test_inconsistent_index_and_chunks_are_detected(tmp_path):
    store, _ = _store(n=4)
    store.save(tmp_path)
    chunks = json.loads((tmp_path / "chunks.json").read_text())
    (tmp_path / "chunks.json").write_text(json.dumps(chunks[:2]))

    with pytest.raises(VectorStoreError, match="inconsistent"):
        VectorStore.load(tmp_path)


def test_corrupt_chunks_file_raises_store_error(tmp_path):
    store, _ = _store()
    store.save(tmp_path)
    (tmp_path / "chunks.json").write_text("{not json")

    with pytest.raises(VectorStoreError):
        VectorStore.load(tmp_path)
