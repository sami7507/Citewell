"""
HTML-building helpers for the Citewell interface.

Everything here is a pure function (no Streamlit import), so it can be unit
tested by checking output strings, with no browser or live app required.

SECURITY: answers and retrieved passages originate from an LLM and from
user-supplied documents, so every piece of text is HTML-escaped before it is
placed inside markup that is rendered with `unsafe_allow_html=True`.
"""

import html
import re
from typing import List, Optional, Set

# Matches "Source 2", "Sources 1 and 3", "Source 1, 2" (numbers are 1-2 digits).
# Works on both raw text and HTML-escaped text (where "&" becomes "&amp;").
_CITATION = r"Sources?\s+(\d{1,2}(?:\s*(?:,|and|&amp;|&)\s*(?:Source\s+)?\d{1,2})*)"
_CITATION_RE = re.compile(_CITATION)
_PAREN_CITATION_RE = re.compile(r"[ \t]*\(\s*" + _CITATION + r"\s*\)")


def _escape(text: str) -> str:
    """Minimal HTML escaping for text embedded in markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def safe_markdown_text(text: str) -> str:
    """
    Escape literal dollar signs before passing text to st.markdown().

    st.markdown() treats text between two "$" characters as LaTeX math, which
    garbles the figures a financial-document assistant constantly produces
    ("$2.29 billion ... $1.33 billion" becomes one run-together expression).
    Escaping "$" as "\\$" always renders a literal currency symbol.
    """
    return text.replace("$", "\\$")


def extract_cited_source_numbers(answer_text: str) -> Set[int]:
    """
    Return which "Source N" citations an answer actually mentions, e.g.
    {1, 3} from "...(Source 1)... (Source 3).", including grouped forms such
    as "Sources 1 and 3".

    Retrieval returns top_k chunks but the answer usually cites only some of
    them; separating "used" from "also retrieved" gives a much clearer signal
    than presenting every chunk as equally relevant. Parsing the model's own
    output avoids a second model call.
    """
    cited: Set[int] = set()
    for match in _CITATION_RE.finditer(answer_text):
        cited.update(int(n) for n in re.findall(r"\d{1,2}", match.group(1)))
    return cited


def format_answer(answer_text: str) -> str:
    """
    Prepare an LLM answer for st.markdown(..., unsafe_allow_html=True).

    1. Escapes HTML, so model output (or text echoed from a document) can never
       inject markup or scripts.
    2. Turns "(Source 2)" style references into small numbered citation marks
       that line up with the numbered passages under the answer.
    3. Escapes "$" so currency is not parsed as math.
    """
    safe = html.escape(answer_text, quote=False)

    def to_marks(match: "re.Match") -> str:
        numbers = re.findall(r"\d{1,2}", match.group(1))
        return "".join(f'<sup class="cw-ref">{n}</sup>' for n in numbers)

    safe = _PAREN_CITATION_RE.sub(to_marks, safe)
    safe = _CITATION_RE.sub(to_marks, safe)
    return safe.replace("$", "\\$")


def render_source_chips(sources: List[str]) -> str:
    """Render citation strings as chips for display via st.markdown(unsafe_allow_html=True)."""
    if not sources:
        return "<em>No sources available.</em>"

    chips = "".join(f'<span class="source-chip">{_escape(s)}</span>' for s in sources)
    return f"<div>{chips}</div>"


def render_evidence_panel(
    evidence: List[dict],
    max_excerpt_length: int = 320,
    cited_indices: Optional[Set[int]] = None,
) -> str:
    """
    Render the retrieved passage behind each citation, not just its label, so
    the grounding of an answer is checkable rather than merely claimed.

    `evidence` is a list of {"label": str, "text": str} in citation order
    ("Source 1" is evidence[0]). When `cited_indices` is given, passages the
    answer actually cited come first, and the rest are grouped under "Other
    retrieved evidence" and de-emphasised, so the relevant excerpt is not
    buried among passages the answer did not use.
    """
    if not evidence:
        return "<em>No evidence available.</em>"

    def _block(item: dict, used: Optional[bool]) -> str:
        label = _escape(item["label"])
        text = item["text"]
        if len(text) > max_excerpt_length:
            text = text[:max_excerpt_length].rsplit(" ", 1)[0] + "…"
        text = _escape(text)
        # used=True -> cited; used=False -> retrieved but not cited; None -> no citation info
        badge = '<span class="evidence-used-badge">★ used in answer</span>' if used else ""
        css_class = "evidence-block unused" if used is False else "evidence-block"
        return (
            f'<div class="{css_class}">'
            f'<div class="evidence-label">{label}{badge}</div>'
            f'<div class="evidence-text">{text}</div>'
            f"</div>"
        )

    if cited_indices is None:
        return "".join(_block(item, used=None) for item in evidence)

    used_items = [item for i, item in enumerate(evidence, start=1) if i in cited_indices]
    other_items = [item for i, item in enumerate(evidence, start=1) if i not in cited_indices]

    result = "".join(_block(item, used=True) for item in used_items)
    if other_items:
        result += '<div class="evidence-section-label">Other retrieved evidence</div>'
        result += "".join(_block(item, used=False) for item in other_items)
    return result


def render_wordmark() -> str:
    """The product wordmark shown at the top of the sidebar."""
    return '<div class="cw-wordmark"><span>Citewell</span></div>'


def friendly_document_name(filename: str) -> str:
    """'sample_lease_agreement.pdf' -> 'Sample lease agreement'."""
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    words = re.sub(r"[_\-]+", " ", stem).strip()
    return (words[:1].upper() + words[1:]) if words else filename
