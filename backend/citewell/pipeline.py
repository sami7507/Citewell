"""
Pipeline orchestration for Citewell.

This module holds the actual pipeline LOGIC (build an index, answer a
question) as plain functions with no CLI or UI concerns. The command-line
tools, the Streamlit app, the evaluation harness and the tests all call these
same functions, so a bug is fixed in one place rather than three.
"""

import logging
from typing import Callable, List, Optional

from citewell import config
from citewell.chunking.chunker import Chunk, clause_aware_chunk
from citewell.embeddings.embedder import Embedder
from citewell.generation.generator import GeneratedAnswer, Generator
from citewell.ingestion.loaders import PageContent, load_documents_from_dir
from citewell.ingestion.table_extractor import extract_tables_from_dir
from citewell.retrieval.retriever import Retriever
from citewell.vectorstore.store import VectorStore

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


def chunk_documents(pages: List[PageContent], table_chunks: List[Chunk]) -> List[Chunk]:
    """
    Combine prose and table chunks into the final list that gets embedded.

    Pages that contain a real table are excluded from prose chunking. pypdf's
    flat text for such a page is a jumbled cell-by-cell dump, and indexing it
    alongside the clean, structure-preserving table chunk would put a garbled
    duplicate of the same financial data in competition with the correct one.
    Pages without tables (e.g. pure-prose MD&A) are unaffected.
    """
    table_pages = {(c.source, c.page_number) for c in table_chunks}
    prose_pages = [p for p in pages if (p.source, p.page_number) not in table_pages]
    return clause_aware_chunk(prose_pages) + table_chunks


def load_and_chunk_documents(source_dir: Optional[str] = None, verbose: bool = False) -> List[Chunk]:
    """
    Load every document in `source_dir`, extract tables, and return the final
    chunk list. Shared by build_index() and the embedding comparison so both
    always chunk identically (a fair comparison needs identical chunks).
    """
    source_dir = source_dir or config.SAMPLE_DOCS_DIR

    if verbose:
        print(f"[1/3] Loading documents from {source_dir} ...")
    pages = load_documents_from_dir(source_dir)
    if verbose:
        print(f"      Loaded {len(pages)} page(s)/section(s).")
        print("[2/3] Extracting tables ...")
    table_chunks = extract_tables_from_dir(source_dir)
    if verbose:
        print(f"      Found {len(table_chunks)} table(s).")
        print("[3/3] Chunking prose (clause-aware) ...")

    all_chunks = chunk_documents(pages, table_chunks)
    if verbose:
        print(f"      Total chunks (prose + table): {len(all_chunks)}")
    return all_chunks


def build_index(
    source_dir: Optional[str] = None,
    save_dir: Optional[str] = None,
    embedder: Optional[Embedder] = None,
    verbose: bool = True,
) -> VectorStore:
    """
    Run the ingestion side of the pipeline (load, chunk, extract tables, embed)
    and build and persist a FAISS index. Run once whenever the document set
    changes; queries then load the saved index via Retriever.from_saved_store().
    """
    save_dir = save_dir or config.VECTORSTORE_DIR
    embedder = embedder or Embedder()

    all_chunks = load_and_chunk_documents(source_dir, verbose=verbose)
    if not all_chunks:
        raise ValueError(f"No readable documents found in '{source_dir or config.SAMPLE_DOCS_DIR}'.")

    if verbose:
        print(f"[4/5] Embedding chunks with '{embedder.model_name}' ...")
    embeddings = embedder.embed_texts([c.text for c in all_chunks], show_progress=verbose)

    if verbose:
        print(f"[5/5] Building and saving FAISS index to {save_dir} ...")
    store = VectorStore(embedding_dim=embedder.embedding_dim, embedding_model=embedder.model_name)
    store.add(all_chunks, embeddings)
    store.save(save_dir)

    if verbose:
        print("Done. Index is ready for querying.")
    return store


def answer_question(
    question: str,
    retriever: Optional[Retriever] = None,
    generator: Optional[Generator] = None,
    top_k: Optional[int] = None,
) -> GeneratedAnswer:
    """
    Run the query-time pipeline: retrieve relevant chunks, then generate a
    grounded, cited answer. Accepting pre-built retriever/generator instances
    matters: the embedding model and the Groq client should be created once and
    reused, not reloaded per call.
    """
    retriever = retriever or Retriever.from_saved_store()
    generator = generator or Generator()

    results = retriever.retrieve(question, top_k=top_k)
    return generator.generate(question, results)
