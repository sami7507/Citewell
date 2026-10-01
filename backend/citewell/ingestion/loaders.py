"""
Document loaders for Citewell.

Legal and financial documents arrive as PDFs (contracts, annual reports) or
DOCX (draft agreements). Each format needs different extraction logic, but
the rest of the pipeline should not care where the text came from. This
module normalises any supported document into a list of `PageContent`
blocks with source metadata attached at extraction time, which is what makes
exact citations possible later without rework.

Failures here are reported as `DocumentLoadError` with a message written for
the person who uploaded the file, not a low-level parser traceback.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from docx import Document as DocxDocument
from pypdf import PdfReader

from citewell import config

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx")

# A DOCX has no pages, so consecutive paragraphs are grouped into sections of
# roughly this size. Headings start a new section sooner.
DOCX_SECTION_TARGET_CHARS = 3000


class DocumentLoadError(ValueError):
    """A document could not be read. The message is safe to show to users."""


@dataclass
class PageContent:
    """One page (or page-equivalent section) of extracted text plus metadata."""

    text: str
    source: str          # original filename, e.g. "sample_lease.pdf"
    page_number: int     # 1-indexed page number (PDF) or section number (DOCX)
    metadata: dict = field(default_factory=dict)


def is_supported(file_path: str | Path) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def _clean(text: str) -> str:
    """Remove NUL bytes and normalise line endings; keep line structure intact."""
    return text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()


def load_pdf(file_path: str | Path) -> List[PageContent]:
    """
    Extract text from a PDF, page by page.

    Page granularity is kept (rather than joining the whole file) so answers
    can cite "page 4 of lease.pdf", the way a lawyer or analyst would expect.
    Pages with no extractable text (blank separators, scanned images) are
    skipped; if that is every page, an empty list is returned and the caller
    decides how to explain it.
    """
    file_path = Path(file_path)
    name = file_path.name

    try:
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception:
                unlocked = 0
            if not unlocked:
                raise DocumentLoadError(f"{name} is password-protected. Remove the password and upload it again.")
        total_pages = len(reader.pages)
    except DocumentLoadError:
        raise
    except Exception as exc:
        raise DocumentLoadError(f"{name} could not be read as a PDF. The file may be damaged.") from exc

    if total_pages > config.MAX_PDF_PAGES:
        raise DocumentLoadError(
            f"{name} has {total_pages} pages, which is over the {config.MAX_PDF_PAGES}-page limit."
        )

    pages: List[PageContent] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = _clean(page.extract_text() or "")
        except Exception:
            logger.warning("Skipping unreadable page %d of %s", number, name, exc_info=True)
            continue
        if not text:
            continue
        pages.append(
            PageContent(
                text=text,
                source=name,
                page_number=number,
                metadata={"file_type": "pdf", "total_pages": total_pages},
            )
        )
    return pages


def _docx_table_to_text(table) -> str:
    """Render a DOCX table as pipe-separated rows so row/column meaning survives."""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _docx_blocks(doc) -> List[tuple]:
    """Return (text, is_heading) for each paragraph/table in document order."""
    blocks = []
    try:
        content = list(doc.iter_inner_content())  # python-docx >= 1.0: paragraphs and tables in order
    except AttributeError:
        content = list(doc.paragraphs)

    for item in content:
        if hasattr(item, "rows"):  # a table
            text = _docx_table_to_text(item)
            if text:
                blocks.append((text, False))
            continue
        text = item.text.strip()
        if not text:
            continue
        style = (getattr(item.style, "name", "") or "").lower()
        blocks.append((text, style.startswith("heading") or style == "title"))
    return blocks


def load_docx(file_path: str | Path) -> List[PageContent]:
    """
    Extract text from a DOCX file.

    DOCX pagination only exists at render time, so paragraphs and tables are
    grouped into sections (a new section starts at a heading, or when the
    current one grows past a few thousand characters). Citations to a DOCX
    therefore read "section N". Grouping, rather than one block per paragraph,
    keeps related text together so clause-aware chunking can see whole clauses.
    """
    file_path = Path(file_path)
    name = file_path.name

    try:
        doc = DocxDocument(str(file_path))
        blocks = _docx_blocks(doc)
    except Exception as exc:
        raise DocumentLoadError(f"{name} could not be read as a Word document. The file may be damaged.") from exc

    sections: List[PageContent] = []
    current: List[str] = []
    current_len = 0
    current_title = ""

    def flush() -> None:
        nonlocal current, current_len, current_title
        if current:
            sections.append(
                PageContent(
                    text=_clean("\n".join(current)),
                    source=name,
                    page_number=len(sections) + 1,
                    metadata={"file_type": "docx", "section_title": current_title},
                )
            )
        current, current_len, current_title = [], 0, ""

    for text, is_heading in blocks:
        if current and (is_heading or current_len >= DOCX_SECTION_TARGET_CHARS):
            flush()
        if is_heading and not current_title:
            current_title = text[:80]
        current.append(text)
        current_len += len(text)
    flush()

    return sections


def load_document(file_path: str | Path) -> List[PageContent]:
    """Dispatch to the right loader by file extension (the single entry point)."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(file_path)
    if suffix == ".docx":
        return load_docx(file_path)
    raise ValueError(
        f"Unsupported file type {suffix} for {file_path.name}. Supported types: .pdf, .docx"
    )


def load_documents_from_dir(dir_path: str | Path) -> List[PageContent]:
    """Load every supported document in a directory (non-recursive, sorted by name)."""
    dir_path = Path(dir_path)
    pages: List[PageContent] = []
    for file_path in sorted(dir_path.iterdir()):
        if file_path.is_file() and not file_path.name.startswith(".") and is_supported(file_path):
            pages.extend(load_document(file_path))
    return pages
