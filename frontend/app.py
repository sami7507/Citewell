"""
Citewell: Streamlit entry point.

Run from the project root:   streamlit run frontend/app.py

This file is UI orchestration only. The testable logic lives in the backend
package (backend/citewell) and the pure HTML helpers in frontend/components.py.

Two document modes:
  * Sample documents: queries the persisted FAISS index over the demo corpus.
  * My documents: builds a fresh in-memory index from the user's uploads, scoped
    to their browser session. Nothing uploaded is stored.
"""

import html
import logging
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _path in (ROOT / "backend", ROOT):  # backend package + the frontend package itself
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import streamlit as st

# Must be the first Streamlit command (even touching st.secrets can render a warning).
st.set_page_config(page_title="Citewell", page_icon="📑", layout="centered")

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.generation.generator import GenerationError, Generator
from citewell.services.demo_index import DemoCorpusMissingError, get_demo_retriever, sample_document_names
from citewell.services.secrets import bridge_secrets_to_env, secrets_file_exists
from citewell.services.uploads import UploadError, process_uploads, uploaded_files_signature
from citewell.storage.feedback import FeedbackEntry, get_feedback_summary, log_feedback
from frontend.auth import available_providers, is_logged_in, render_account_panel
from frontend.components import (
    extract_cited_source_numbers,
    format_answer,
    friendly_document_name,
    render_evidence_panel,
    render_footer,
    render_info_sections,
    render_page_anchor,
    render_source_chips,
    render_wordmark,
)
from frontend.theme import CUSTOM_CSS
from frontend.welcome import render_welcome

# Only touch st.secrets when a real secrets file exists (see services/secrets.py).
if secrets_file_exists():
    bridge_secrets_to_env(st.secrets)

config.configure_logging()
config.ensure_dirs()
logger = logging.getLogger("citewell.app")

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

# Optional sign-in (Google, and phone when an identity provider for it is configured).
auth_providers = available_providers()
signed_in = is_logged_in()

SAMPLE_MODE, UPLOAD_MODE = "Sample documents", "My documents"

EXAMPLE_QUESTIONS = [
    "What is the monthly rent and when is it due?",
    "Can the tenant keep a pet?",
    "What happens if a loan payment is more than 30 days late?",
    "What was net income for fiscal 2024 according to the income statement?",
]


# ----------------------------------------------------------------------------
# Cached, expensive resources
# ----------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def load_embedder() -> Embedder:
    return Embedder()


@st.cache_resource(show_spinner=False)
def load_demo_retriever(_embedder: Embedder):
    # Leading underscore: Streamlit should not try to hash the embedder.
    return get_demo_retriever(_embedder)


def resolve_generator():
    """
    Build the answer generator from a key in the environment or one pasted into
    the page. A pasted key lives only in this browser session's memory; it is
    never written to disk or logged, and the generator is deliberately not put
    in the shared cache.
    """
    key = st.session_state.get("user_api_key") or config.GROQ_API_KEY
    if not key:
        return None
    cached = st.session_state.get("_generator")
    if cached and cached[0] == key:
        return cached[1]
    try:
        generator = Generator(api_key=key)
    except Exception:
        logger.exception("Could not initialise the generator")
        return None
    st.session_state["_generator"] = (key, generator)
    return generator


# ----------------------------------------------------------------------------
# Session state helpers
# ----------------------------------------------------------------------------

def init_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("rated", {})


def reset_conversation() -> None:
    st.session_state.messages = []
    st.session_state.rated = {}


def forget_api_key() -> None:
    for key in ("user_api_key", "_generator"):
        st.session_state.pop(key, None)


def submit_question() -> None:
    """Runs on Enter in the ask box and on the Ask button: queue the text and clear the box."""
    text = (st.session_state.get("ask_text") or "").strip()
    if text:
        st.session_state["pending_question"] = text
    st.session_state["ask_text"] = ""


def on_attach_change() -> None:
    """When files are attached, search them instead of the sample documents."""
    if st.session_state.get("attach_files"):
        st.session_state["mode"] = UPLOAD_MODE


def enter_as_guest() -> None:
    st.session_state["guest"] = True


def ask_example(question: str) -> None:
    st.session_state["pending_question"] = question


def rate_answer(message_id: str, rating: str) -> None:
    message = next((m for m in st.session_state.messages if m["id"] == message_id), None)
    if message is None or message_id in st.session_state.rated:
        return
    try:
        log_feedback(
            FeedbackEntry(
                question=message["question"],
                answer=message["answer"],
                sources=[e["label"] for e in message["evidence"]],
                rating=rating,
                mode=message["mode"],
                top_k=message["top_k"],
            )
        )
        st.session_state.rated[message_id] = rating
    except Exception:
        logger.exception("Could not save feedback")
        st.session_state["feedback_error"] = True


init_state()

# ----------------------------------------------------------------------------
# Welcome (sign-in) page: the first screen when sign-in is configured
# ----------------------------------------------------------------------------

guest_allowed = not config.REQUIRE_LOGIN
is_guest = guest_allowed and st.session_state.get("guest", False)
needs_welcome = (bool(auth_providers) and not signed_in and not is_guest) or (
    config.REQUIRE_LOGIN and not auth_providers and not signed_in
)
if needs_welcome:
    render_welcome(auth_providers, allow_guest=guest_allowed, on_guest=enter_as_guest)
    st.stop()



# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------

with st.sidebar:
    st.markdown(render_wordmark(), unsafe_allow_html=True)
    st.markdown('<div class="cw-tagline">Answers from your documents, each one cited.</div>', unsafe_allow_html=True)

    if auth_providers:
        render_account_panel(auth_providers, is_guest=is_guest)

    st.markdown('<div class="cw-side-label">Documents</div>', unsafe_allow_html=True)
    mode = st.radio("Documents to search", [SAMPLE_MODE, UPLOAD_MODE], key="mode", label_visibility="collapsed")
    if st.session_state.get("_last_mode") != mode:
        reset_conversation()  # never let an old answer's sources look like they came from the new set
        st.session_state["_last_mode"] = mode

    # Files come from the paperclip next to the ask box (its widget state is available here).
    uploaded_files = st.session_state.get("attach_files") or []
    if mode == UPLOAD_MODE:
        if uploaded_files:
            rows = "".join(f"<div>{html.escape(f.name)}</div>" for f in uploaded_files)
            st.markdown(f'<div class="cw-doc-list">{rows}</div>', unsafe_allow_html=True)
            st.caption("Add more with the paperclip beside the ask box.")
        else:
            st.caption(
                "No documents yet. Use the paperclip beside the ask box to add PDF or Word files. "
                "They are read in memory for this session only and are not saved."
            )
    else:
        names = sample_document_names()
        if names:
            rows = "".join(f"<div>{friendly_document_name(n)}</div>" for n in names)
            st.markdown(f'<div class="cw-doc-list">{rows}</div>', unsafe_allow_html=True)

    st.markdown('<div class="cw-side-label">Search</div>', unsafe_allow_html=True)
    default_k = config.TOP_K if mode == SAMPLE_MODE else config.UPLOAD_TOP_K
    top_k = st.slider(
        "Passages per answer",
        min_value=1,
        max_value=6,
        value=min(default_k, 6),
        key=f"top_k_{mode}",
    )
    st.caption("How many passages the answer is based on. The sample set works best with 2; longer uploads usually need 4 or more.")
    # Relevance filtering only applies to uploads; the sample set keeps its measured behaviour.
    min_score = config.MIN_RELEVANCE_SCORE if mode == UPLOAD_MODE else None

    if st.session_state.messages:
        st.button("New conversation", on_click=reset_conversation, use_container_width=True)
    if st.session_state.get("user_api_key"):
        st.button("Remove my API key", on_click=forget_api_key, use_container_width=True)

    try:
        summary = get_feedback_summary()
        if summary["up"] or summary["down"]:
            st.caption(f"Feedback so far: {summary['up']} helpful, {summary['down']} not helpful")
    except Exception:
        logger.warning("Could not read feedback summary", exc_info=True)


# ----------------------------------------------------------------------------
# Resolve what we can search
# ----------------------------------------------------------------------------

try:
    with st.spinner("Loading the search model. The first run downloads about 90 MB."):
        embedder = load_embedder()
except Exception:
    logger.exception("Embedding model failed to load")
    st.error(
        "The search model could not be loaded. The first run needs an internet connection to download it. "
        "Check your connection and reload the page."
    )
    st.stop()

active_retriever = None
notice = None  # (level, text)

if mode == SAMPLE_MODE:
    try:
        with st.spinner("Preparing the sample documents. This only happens once."):
            active_retriever = load_demo_retriever(embedder)
    except DemoCorpusMissingError as exc:
        notice = ("warning", str(exc))
    except Exception:
        logger.exception("Sample index failed to load")
        notice = ("error", "The sample documents could not be prepared. See the terminal for details.")
else:
    if not uploaded_files:
        notice = ("info", "Click the paperclip beside the ask box to add one or more PDF or Word files.")
    else:
        signature = uploaded_files_signature(uploaded_files)
        if st.session_state.get("_upload_sig") != signature:
            st.session_state["_upload_retriever"] = None
            st.session_state["_upload_summary"] = None
            st.session_state["_upload_error"] = None
            progress_bar = st.progress(0.0, text="Reading your documents")
            try:
                retriever, upload_summary = process_uploads(
                    uploaded_files,
                    embedder,
                    on_progress=lambda fraction, message: progress_bar.progress(min(fraction, 1.0), text=message),
                )
                st.session_state["_upload_retriever"] = retriever
                st.session_state["_upload_summary"] = upload_summary
                reset_conversation()
            except UploadError as exc:
                st.session_state["_upload_error"] = str(exc)
            except Exception:
                logger.exception("Upload processing failed")
                st.session_state["_upload_error"] = "Something went wrong while reading the files. Please try again."
            finally:
                progress_bar.empty()
            st.session_state["_upload_sig"] = signature

        active_retriever = st.session_state.get("_upload_retriever")
        if st.session_state.get("_upload_error"):
            notice = ("error", st.session_state["_upload_error"])

generator = resolve_generator()


# ----------------------------------------------------------------------------
# Main area
# ----------------------------------------------------------------------------

st.markdown(render_page_anchor() + '<div class="cw-title">Ask your documents</div>', unsafe_allow_html=True)

if mode == UPLOAD_MODE and st.session_state.get("_upload_summary"):
    info = st.session_state["_upload_summary"]
    count = len(info.files)
    st.markdown(
        f'<div class="cw-status">Searching {count} file{"s" if count != 1 else ""} '
        f"({info.num_chunks} passages, {info.num_tables} tables).</div>",
        unsafe_allow_html=True,
    )
    for filename, reason in info.skipped:
        st.warning(f"{filename} was skipped. {reason}")
elif mode == SAMPLE_MODE and active_retriever is not None:
    st.markdown(
        f'<div class="cw-status">Searching {len(sample_document_names())} sample documents: '
        f"a lease, a loan agreement, a 10-K excerpt and financial statements.</div>",
        unsafe_allow_html=True,
    )

if notice:
    getattr(st, notice[0])(notice[1])

if generator is None:
    with st.container(border=True):
        st.markdown("**This demo needs a free Groq key to write answers.**")
        st.markdown(
            "1. Create a free key at [console.groq.com/keys](https://console.groq.com/keys).\n"
            "2. Paste it below. It stays in this browser session only and is never saved."
        )
        pasted = st.text_input("Groq API key", type="password", placeholder="gsk_...")
        if pasted.strip():
            st.session_state["user_api_key"] = pasted.strip()
            st.rerun()
        st.caption(
            "Running your own copy? On Streamlit Cloud add GROQ_API_KEY under Settings, then Secrets. "
            "On your computer put it in the .env file. Visitors then never see this box."
        )


def render_exchange(message: dict) -> None:
    """Draw one question and its cited answer."""
    with st.chat_message("user"):
        st.markdown(message["question"].replace("$", "\\$"))

    with st.chat_message("assistant"):
        st.markdown(format_answer(message["answer"]), unsafe_allow_html=True)
        if message.get("model") and message["model"] != config.GROQ_MODEL:
            st.caption(f"Answered by the backup model ({message['model']}) because the main model was unavailable.")

        evidence = message["evidence"]
        if evidence:
            cited = extract_cited_source_numbers(message["answer"])
            title = f"Sources: {len(cited)} cited, {len(evidence)} retrieved" if cited else f"Sources: {len(evidence)} retrieved"
            st.markdown(f'<div class="cw-sources-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(
                render_evidence_panel(evidence, max_excerpt_length=600, cited_indices=cited),
                unsafe_allow_html=True,
            )

        rated = st.session_state.rated.get(message["id"])
        if rated:
            st.caption("Thanks, your feedback was recorded.")
        else:
            col_up, col_down, _ = st.columns([0.15, 0.2, 0.65])
            col_up.button("Helpful", key=f"up_{message['id']}", on_click=rate_answer, args=(message["id"], "up"))
            col_down.button("Not helpful", key=f"down_{message['id']}", on_click=rate_answer, args=(message["id"], "down"))


# ---------------------------------------------------------------- the app: ask box, examples, answers
can_ask = active_retriever is not None and generator is not None

# The ask row sits in the page (not pinned to the screen), so it can never float over the
# information sections below it. Enter or the Ask button submits; the paperclip adds files.
ask_columns = st.columns([8, 1.3, 0.8], vertical_alignment="center")
with ask_columns[0]:
    st.text_input(
        "Your question",
        key="ask_text",
        placeholder="Ask a question about the documents",
        label_visibility="collapsed",
        max_chars=config.MAX_QUESTION_CHARS,
        disabled=not can_ask,
        on_change=submit_question,
    )
with ask_columns[1]:
    st.button("Ask", key="ask_button", type="primary", use_container_width=True, disabled=not can_ask, on_click=submit_question)
with ask_columns[2]:
    with st.container(key="attach_wrap"):
        with st.popover("Attach", icon=":material/attach_file:", use_container_width=True):
            st.markdown("**Use your own documents**")
            st.file_uploader(
                "PDF or Word files",
                type=["pdf", "docx"],
                accept_multiple_files=True,
                key="attach_files",
                on_change=on_attach_change,
                label_visibility="collapsed",
            )
            st.caption(
                f"Up to {config.MAX_UPLOAD_FILES} files, {config.MAX_UPLOAD_MB} MB each. "
                "Files are read in memory for this session only and are not saved."
            )

question = st.session_state.pop("pending_question", None)

if st.session_state.pop("feedback_error", False):
    st.warning("Your feedback could not be saved right now.")

# Suggested questions, shown until the first question is asked.
if can_ask and mode == SAMPLE_MODE and not st.session_state.messages and not question:
    st.markdown('<div class="cw-try">Or try one of these</div>', unsafe_allow_html=True)
    example_columns = st.columns(2)
    for index, example in enumerate(EXAMPLE_QUESTIONS):
        example_columns[index % 2].button(
            example, key=f"example_{index}", on_click=ask_example, args=(example,), use_container_width=True
        )

using_shared_key = not st.session_state.get("user_api_key")
question_limit = config.MAX_QUESTIONS_SIGNED_IN if signed_in else config.MAX_QUESTIONS_PER_SESSION
session_limit_reached = (
    using_shared_key
    and question_limit > 0
    and st.session_state.get("asked_count", 0) >= question_limit
)

if question and can_ask and session_limit_reached:
    st.info(
        f"This demo allows {question_limit} questions per session to protect its free quota. "
        + ("" if signed_in or not auth_providers else "Signing in raises the limit. ")
        + "You can also refresh the page to start a new session, or paste your own free Groq key to remove the limit."
    )
    question = None

if question and can_ask:
    try:
        with st.spinner("Reading the documents"):
            results = active_retriever.retrieve(question, top_k=top_k, min_score=min_score)
            generated = generator.generate(question, results)
    except GenerationError as exc:
        st.error(str(exc))
    except Exception:
        logger.exception("Answering failed")
        st.error("Something went wrong while answering. Please try again.")
    else:
        st.session_state["asked_count"] = st.session_state.get("asked_count", 0) + 1
        st.session_state.messages.append(
            {
                "id": uuid.uuid4().hex[:12],
                "question": question,
                "answer": generated.answer,
                "evidence": [{"label": lbl, "text": r.chunk.text} for lbl, r in zip(generated.sources_used, results)],
                "mode": mode,
                "top_k": top_k,
                "model": generated.model,
            }
        )

# Newest answer first, directly under the ask box, like search results.
for message in reversed(st.session_state.messages):
    render_exchange(message)

# ---------------------------------------------------------------- the website: information, then footer
st.markdown(
    render_info_sections(login_enabled=bool(auth_providers), login_required=config.REQUIRE_LOGIN and bool(auth_providers)),
    unsafe_allow_html=True,
)
st.markdown(render_footer(), unsafe_allow_html=True)
