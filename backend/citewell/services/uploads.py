"""
Turn user-uploaded files into an in-memory, session-scoped retriever.

Nothing uploaded is kept: files land in a temporary directory that is removed
afterwards (success or failure), and the resulting index lives only in memory.

Security and reliability measures applied before any parser sees a file:
  * the number and size of files are capped;
  * only .pdf and .docx are accepted, and the file's leading bytes must match
    its extension (a renamed .exe is rejected);
  * filenames are reduced to a safe basename, so "../../x.pdf" can never write
    outside the temp directory;
  * each file is processed independently, so one bad file is reported by name
    instead of failing the whole batch.
"""

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.ingestion.loaders import DocumentLoadError, load_document
from citewell.ingestion.table_extractor import extract_tables_from_pdf
from citewell.pipeline import chunk_documents
from citewell.retrieval.retriever import Retriever
from citewell.vectorstore.store import VectorStore

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX files are ZIP containers


class UploadError(ValueError):
    """The upload cannot be used. The message is safe to show to users."""


@dataclass
class UploadSummary:
    """What was indexed, for display in the UI."""

    files: List[str] = field(default_factory=list)
    num_chunks: int = 0
    num_tables: int = 0
    skipped: List[Tuple[str, str]] = field(default_factory=list)  # (filename, reason)


def uploaded_files_signature(uploaded_files) -> tuple:
    """
    An order-independent fingerprint (name + size) of the upload set, so the
    index is only rebuilt when the files actually change, not on every
    Streamlit rerun.
    """
    return tuple(sorted((f.name, f.size) for f in uploaded_files))


def safe_filename(name: str) -> str:
    """Reduce an arbitrary client-supplied filename to a safe basename."""
    base = Path(str(name).replace("\\", "/")).name
    base = re.sub(r"[^\w.\- ()]", "_", base).strip(" .")
    return base or "document"


def _check_batch(uploaded_files) -> None:
    if not uploaded_files:
        raise UploadError("Choose at least one PDF or Word document.")
    if len(uploaded_files) > config.MAX_UPLOAD_FILES:
        raise UploadError(f"Upload at most {config.MAX_UPLOAD_FILES} files at a time.")


def _check_file(uploaded_file, content_head: bytes) -> Optional[str]:
    """Return a reason string if the file is unusable, else None."""
    name = safe_filename(uploaded_file.name)
    suffix = Path(name).suffix.lower()
    size = getattr(uploaded_file, "size", 0)

    if suffix not in (".pdf", ".docx"):
        return "Only PDF and Word (.docx) files are supported."
    if size == 0:
        return "The file is empty."
    if size > config.MAX_UPLOAD_MB * 1024 * 1024:
        return f"The file is larger than {config.MAX_UPLOAD_MB} MB."
    expected = _PDF_MAGIC if suffix == ".pdf" else _ZIP_MAGIC
    if not content_head.startswith(expected):
        return f"The file content does not look like a real {suffix[1:].upper()}."
    return None


def process_uploads(
    uploaded_files,
    embedder: Embedder,
    on_progress: Optional[ProgressCallback] = None,
) -> Tuple[Retriever, UploadSummary]:
    """
    Build a retriever from uploaded files and report what happened.

    Accepts any objects exposing `.name`, `.size` and `.getbuffer()` (which is
    what Streamlit's UploadedFile provides), so it is testable with fakes.
    Raises UploadError if nothing usable could be extracted.
    """
    _check_batch(uploaded_files)
    progress = on_progress or (lambda fraction, message: None)
    summary = UploadSummary()
    pages, table_chunks = [], []
    used_names = set()

    tmpdir = tempfile.mkdtemp(prefix="citewell_upload_")
    try:
        total = len(uploaded_files)
        for i, uploaded_file in enumerate(uploaded_files):
            name = safe_filename(uploaded_file.name)
            progress(i / total * 0.6, f"Reading {name}")

            data = uploaded_file.getbuffer()
            reason = _check_file(uploaded_file, bytes(data[:4]))
            if reason:
                summary.skipped.append((name, reason))
                continue

            # Keep names unique so two files called "contract.pdf" do not collide.
            unique, counter = name, 1
            while unique.lower() in used_names:
                counter += 1
                unique = f"{Path(name).stem} ({counter}){Path(name).suffix}"
            used_names.add(unique.lower())

            dest = Path(tmpdir) / unique
            with open(dest, "wb") as handle:
                handle.write(data)

            try:
                file_pages = load_document(dest)
                file_tables = extract_tables_from_pdf(dest) if dest.suffix.lower() == ".pdf" else []
            except DocumentLoadError as exc:
                summary.skipped.append((unique, str(exc)))
                continue
            except Exception:
                logger.exception("Unexpected failure while reading %s", unique)
                summary.skipped.append((unique, "The file could not be processed."))
                continue

            if not file_pages and not file_tables:
                summary.skipped.append((
                    unique,
                    "No text could be extracted. It may be a scanned image; Citewell does not read scanned pages yet.",
                ))
                continue

            pages.extend(file_pages)
            table_chunks.extend(file_tables)
            summary.files.append(unique)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not summary.files:
        detail = " ".join(f"{n}: {r}" for n, r in summary.skipped)
        raise UploadError(f"None of the files could be used. {detail}".strip())

    progress(0.65, "Splitting into passages")
    chunks = chunk_documents(pages, table_chunks)
    if not chunks:
        raise UploadError("No text could be extracted from the uploaded file(s).")

    progress(0.75, "Building the search index")
    embeddings = embedder.embed_texts([c.text for c in chunks])
    store = VectorStore(
        embedding_dim=embedder.embedding_dim,
        embedding_model=getattr(embedder, "model_name", None),
    )
    store.add(chunks, embeddings)

    summary.num_chunks = len(chunks)
    summary.num_tables = len(table_chunks)
    progress(1.0, "Ready")
    return Retriever(embedder=embedder, vectorstore=store), summary


def build_retriever_from_uploads(uploaded_files, embedder: Embedder) -> Retriever:
    """Convenience wrapper returning just the retriever (see process_uploads)."""
    retriever, _ = process_uploads(uploaded_files, embedder)
    return retriever
