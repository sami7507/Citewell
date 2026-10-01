"""Load the persisted sample-document index, rebuilding it when needed."""

import logging

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.ingestion.loaders import is_supported
from citewell.pipeline import build_index
from citewell.retrieval.retriever import Retriever
from citewell.vectorstore.store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)


class DemoCorpusMissingError(RuntimeError):
    """There are no sample documents to index. The message is safe to show to users."""


def sample_document_names() -> list:
    """Filenames of the sample documents currently on disk."""
    directory = config.SAMPLE_DOCS_DIR
    if not directory.exists():
        return []
    return sorted(p.name for p in directory.iterdir() if p.is_file() and is_supported(p))


def get_demo_retriever(embedder: Embedder) -> Retriever:
    """
    Return a retriever over the sample documents.

    The saved index is reused when it is valid and was built with the same
    embedding model. It is rebuilt automatically when it is missing, corrupt,
    in an older format, or built with a different model (which would otherwise
    produce a dimension error or silently poor results).
    """
    try:
        store = VectorStore.load()
        if store.embedding_model == embedder.model_name:
            return Retriever(embedder=embedder, vectorstore=store)
        logger.info("Embedding model changed (%s -> %s); rebuilding index", store.embedding_model, embedder.model_name)
    except (FileNotFoundError, VectorStoreError) as exc:
        logger.info("Building sample index: %s", exc)

    if not sample_document_names():
        raise DemoCorpusMissingError(
            f"No sample documents were found in {config.SAMPLE_DOCS_DIR}. "
            f"Add PDF or DOCX files there, or switch to your own documents."
        )

    build_index(embedder=embedder, verbose=False)
    return Retriever(embedder=embedder, vectorstore=VectorStore.load())
