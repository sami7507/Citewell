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


def _tidy_excerpt(text: str) -> str:
    """PDF line breaks are not paragraph breaks, so join them; leave markdown tables as they are."""
    if "\n|" in text or text.lstrip().startswith("|") or text.startswith("Table "):
        return text
    return re.sub(r"[ \t]*\n[ \t]*", " ", text).strip()


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
        text = _tidy_excerpt(item["text"])
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
    """'sample_lease_agreement.pdf' -> 'Sample lease agreement'; '10k' reads as '10-K'."""
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)
    words = re.sub(r"[_\-]+", " ", stem).strip()
    words = re.sub(r"\b10k\b", "10-K", words, flags=re.IGNORECASE)
    return (words[:1].upper() + words[1:]) if words else filename


# ---------------------------------------------------------------- site sections and footer
# Static copy only (no user or model text), built as compact single-line HTML because
# Streamlit's markdown treats indented or blank-line-separated HTML as code.

REPO_URL = "https://github.com/sami7507/citewell"
LINKEDIN_URL = "https://www.linkedin.com/in/sami7507"
EMAIL = "sami757007@gmail.com"

_HOW_IT_WORKS = [
    ("1", "Ask", "Type a question in plain English, or pick one of the examples."),
    ("2", "Find", "Citewell searches the documents and pulls out the few passages that matter most."),
    ("3", "Answer", "A language model writes the answer using only those passages, and cites each one."),
]

_FEATURES = [
    ("Cited answers", "Numbered marks match the passages shown under each answer, so you can check every claim."),
    ("Built for contracts", "Numbered clauses stay whole, so a rent figure is never separated from the word rent."),
    ("Reads real tables", "Financial statements keep their rows and columns, so a number stays with its label and year."),
    ("Honest about gaps", "If the documents do not contain the answer, it says so instead of guessing."),
    ("Your own files", "Upload PDF or Word documents and ask about them in the same session."),
    ("Measured quality", "Retrieval and answer faithfulness are scored against a hand-labelled question set."),
]


def render_info_sections(login_enabled: bool = False, login_required: bool = False) -> str:
    """The 'how it works / what you get / privacy / limits' sections shown before the first question."""
    steps = "".join(
        f'<div class="cw-card"><div class="cw-step">{n}</div><div class="cw-card-title">{t}</div><div class="cw-card-body">{b}</div></div>'
        for n, t, b in _HOW_IT_WORKS
    )
    feats = "".join(
        f'<div class="cw-card"><div class="cw-card-title">{t}</div><div class="cw-card-body">{b}</div></div>'
        for t, b in _FEATURES
    )
    if not login_enabled:
        account_line = "There are no accounts and no sign-in."
    elif login_required:
        account_line = "Signing in is required. Citewell does not store your name, email or phone number."
    else:
        account_line = "Signing in is optional and only raises your question limit. Citewell does not store your name, email or phone number."
    privacy = (
        '<div class="cw-note"><div class="cw-card-title">Privacy</div><ul>'
        "<li>Files you upload are read in memory for your session and are not saved.</li>"
        "<li>Your question and the matching passages are sent to Groq, the service that writes the answer.</li>"
        "<li>If you rate an answer, the question, answer and sources are saved to help improve the project.</li>"
        f"<li>{account_line}</li></ul></div>"
    )
    limits = (
        '<div class="cw-note"><div class="cw-card-title">Good to know</div><ul>'
        "<li>Citewell is a reading aid, not legal or financial advice.</li>"
        "<li>Answers can contain mistakes. Always check the passage shown under the answer.</li>"
        "<li>Scanned, image-only PDFs cannot be read yet.</li>"
        "<li>The sample documents are fictional and for demonstration only.</li></ul></div>"
    )
    return (
        '<div class="cw-info">'
        '<div class="cw-section"><div class="cw-section-title">How it works</div>'
        f'<div class="cw-cards cw-cards-3">{steps}</div></div>'
        '<div class="cw-section"><div class="cw-section-title">What you get</div>'
        f'<div class="cw-cards cw-cards-3">{feats}</div></div>'
        f'<div class="cw-section"><div class="cw-cards cw-cards-2">{privacy}{limits}</div></div>'
        "</div>"
    )


PROFILE_URL = "https://github.com/sami7507"

# Every link below goes somewhere real. A footer full of dead links looks worse than a small one.
_FOOTER_COLUMNS = [
    ("Project", [
        ("Source code", REPO_URL),
        ("Documentation", REPO_URL + "#readme"),
        ("Architecture notes", REPO_URL + "/blob/HEAD/docs/ARCHITECTURE.md"),
        ("Report an issue", REPO_URL + "/issues"),
    ]),
    ("Built with", [
        ("Streamlit", "https://streamlit.io"),
        ("Groq", "https://groq.com"),
        ("FAISS", "https://github.com/facebookresearch/faiss"),
        ("Sentence Transformers", "https://www.sbert.net"),
    ]),
    ("Connect", [
        ("LinkedIn", LINKEDIN_URL),
        ("GitHub", PROFILE_URL),
        ("Email", f"mailto:{EMAIL}"),
    ]),
]


def _footer_link(text: str, href: str) -> str:
    external = href.startswith("http")
    attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    return f'<a href="{href}"{attrs}>{text}</a>'


def render_page_anchor() -> str:
    """Invisible target at the top of the page for the footer's 'Back to top' bar."""
    return '<div id="cw-top"></div>'


def render_footer() -> str:
    """
    Full-width site footer: a 'Back to top' bar, a brand column and three link columns,
    and a closing line with the disclaimer and privacy summary. CSS (theme.py) stretches
    it edge to edge and pins it to the bottom of the page.
    """
    columns = "".join(
        f'<div class="cw-footer-col"><div class="cw-footer-head">{title}</div>'
        + "".join(_footer_link(text, href) for text, href in links)
        + "</div>"
        for title, links in _FOOTER_COLUMNS
    )
    return (
        '<div class="cw-footer-full">'
        '<a class="cw-top" href="#cw-top">Back to top</a>'
        '<div class="cw-footer-inner">'
        '<div class="cw-footer-grid">'
        '<div class="cw-footer-about"><div class="cw-footer-brand"><span>Citewell</span></div>'
        "<p>Ask your contracts and financial filings anything. Every answer shows the passage it came from.</p></div>"
        f"{columns}"
        "</div>"
        '<div class="cw-footer-bar">'
        "Citewell is a portfolio project by Sami. It is a reading aid, not legal or financial advice. "
        "Files you upload are read in memory and never stored."
        "</div></div></div>"
    )


# ---------------------------------------------------------------- sign-in (welcome) page

def render_welcome_brand() -> str:
    """Left third of the sign-in page: logo, promise, three points and a small illustration. Static HTML only."""
    lines = [(30, 150), (48, 170), (66, 150), (84, 120), (102, 165), (120, 90)]
    rows = "".join(
        f'<rect x="22" y="{y}" width="{w}" height="5" rx="2.5" fill="#C9D2CE"/>' for i, (y, w) in enumerate(lines) if i != 2
    )
    sheet = (
        '<svg class="cw-welcome-sheet" viewBox="0 0 220 150" role="img" aria-label="A document with one highlighted, cited line">'
        '<rect x="8" y="8" width="204" height="134" rx="8" fill="#FFFFFF"/>'
        f"{rows}"
        '<rect x="20" y="63" width="152" height="11" rx="2" fill="#FFE066"/>'
        '<rect x="22" y="66" width="140" height="5" rx="2.5" fill="#C9D2CE"/>'
        '<rect x="178" y="60" width="20" height="17" rx="3" fill="#FFE066"/>'
        '<text x="188" y="72.5" text-anchor="middle" font-size="11" font-weight="700" fill="#14201C" font-family="sans-serif">1</text>'
        "</svg>"
    )
    points = "".join(
        f'<li><span class="cw-welcome-dot"></span>{text}</li>'
        for text in (
            "Every answer is cited to its clause, table or page",
            "It says so when the answer is not in the documents",
            "Files you upload are never stored",
        )
    )
    return (
        '<div class="cw-welcome-brand">'
        '<div class="cw-welcome-top">'
        '<div class="cw-welcome-logo"><span>Citewell</span></div>'
        '<div class="cw-welcome-promise">Answers you can check.</div>'
        '<p class="cw-welcome-sub">Ask your contracts and financial filings anything. Every answer shows the passage it came from.</p>'
        f'<ul class="cw-welcome-points">{points}</ul>'
        "</div>"
        f'<div class="cw-welcome-art">{sheet}</div>'
        '<div class="cw-welcome-credit">A portfolio project by Sami</div>'
        "</div>"
    )


def render_welcome_heading(required: bool = False) -> str:
    """Heading block for the right side of the sign-in page."""
    sub = (
        "Sign in to continue."
        if required
        else "Sign in to ask questions and get a higher question limit, or look around as a guest."
    )
    return (
        '<div class="cw-welcome-right-space"></div>'
        '<div class="cw-welcome-title">Sign in to Citewell</div>'
        f'<div class="cw-welcome-lede">{sub}</div>'
    )


def render_welcome_fineprint() -> str:
    return (
        '<div class="cw-welcome-fine">Signing in only confirms who you are. '
        "Citewell does not store your name, email or phone number.</div>"
    )
