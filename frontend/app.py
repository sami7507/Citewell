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
st.set_page_config(page_title="Citewell: cited answers from your documents", page_icon="📑", layout="centered")

from citewell import config
from citewell.embeddings.embedder import Embedder
from citewell.generation.generator import GenerationError, Generator
from citewell.services.demo_index import DemoCorpusMissingError, get_demo_retriever, sample_document_names
from citewell.services.secrets import bridge_secrets_to_env, secrets_file_exists
from citewell.services.uploads import UploadError, process_uploads, uploaded_files_signature
from citewell.storage.feedback import FeedbackEntry, get_feedback_summary, log_feedback
from frontend.components import (
    extract_cited_source_numbers,
    format_answer,
    friendly_document_name,
    render_evidence_panel,
    render_source_chips,
    render_wordmark,
)
from frontend.theme import CUSTOM_CSS

# Only touch st.secrets when a real secrets file exists (see services/secrets.py).
if secrets_file_exists():
    bridge_secrets_to_env(st.secrets)

config.configure_logging()
config.ensure_dirs()
logger = logging.getLogger("citewell.app")

st.markdown(f"<style>{CUSTOM_CSS}</style>", unsafe_allow_html=True)

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
# Sidebar
# ----------------------------------------------------------------------------

with st.sidebar:
    st.markdown(render_wordmark(), unsafe_allow_html=True)
    st.markdown('<div class="cw-tagline">Answers from your documents, each one cited.</div>', unsafe_allow_html=True)

    mode = st.radio("Documents to search", [SAMPLE_MODE, UPLOAD_MODE], key="mode")
    if st.session_state.get("_last_mode") != mode:
        reset_conversation()  # never let an old answer's sources look like they came from the new set
        st.session_state["_last_mode"] = mode

    uploaded_files = None
    if mode == UPLOAD_MODE:
        uploaded_files = st.file_uploader(
            "Add PDF or Word files",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            help=f"Up to {config.MAX_UPLOAD_FILES} files, {config.MAX_UPLOAD_MB} MB each.",
        )
        st.caption("Files are read in memory for this session only. They are not saved.")
    else:
        names = sample_document_names()
        if names:
            rows = "".join(f"<div>{friendly_document_name(n)}</div>" for n in names)
            st.markdown(f'<div class="cw-doc-list">{rows}</div>', unsafe_allow_html=True)

    st.divider()

    default_k = config.TOP_K if mode == SAMPLE_MODE else config.UPLOAD_TOP_K
    with st.expander("Search settings"):
        top_k = st.slider(
            "Passages per answer",
            min_value=1,
            max_value=6,
            value=min(default_k, 6),
            key=f"top_k_{mode}",
            help=(
                "How many passages are given to the model. The sample set works best with 2 "
                "(measured on that corpus). Longer uploaded documents usually need 4 or more."
            ),
        )
        st.caption(f"Embeddings: `{config.EMBEDDING_MODEL.split('/')[-1]}`")
        st.caption(f"Language model: `{config.GROQ_MODEL}`")
    # Relevance filtering only applies to uploads; the sample set keeps its measured behaviour.
    min_score = config.MIN_RELEVANCE_SCORE if mode == UPLOAD_MODE else None

    if st.session_state.messages:
        st.button("New conversation", on_click=reset_conversation, use_container_width=True)

    try:
        summary = get_feedback_summary()
        if summary["up"] or summary["down"]:
            st.caption(f"Feedback so far: {summary['up']} helpful, {summary['down']} not helpful")
    except Exception:
        logger.warning("Could not read feedback summary", exc_info=True)

    with st.expander("About"):
        st.markdown(
            "Built by **Sami**.\n\n"
            "[sami757007@gmail.com](mailto:sami757007@gmail.com)\n\n"
            "[LinkedIn](https://www.linkedin.com/in/sami7507)"
        )


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
        notice = ("info", "Add one or more documents in the sidebar to start asking questions.")
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

st.markdown('<div class="cw-title">Ask your documents</div>', unsafe_allow_html=True)

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
        st.markdown("**One quick setup step.** Answers are written by a free Groq-hosted model, which needs a key.")
        st.markdown(
            "1. Create a free key at [console.groq.com/keys](https://console.groq.com/keys).\n"
            "2. Paste it below. It stays in this browser session only.\n\n"
            "To keep it permanently, add `GROQ_API_KEY` to the `.env` file (see the README)."
        )
        pasted = st.text_input("Groq API key", type="password", placeholder="gsk_...")
        if pasted.strip():
            st.session_state["user_api_key"] = pasted.strip()
            st.rerun()


def render_exchange(message: dict) -> None:
    """Draw one question and its cited answer."""
    with st.chat_message("user"):
        st.markdown(message["question"].replace("$", "\\$"))

    with st.chat_message("assistant"):
        st.markdown(format_answer(message["answer"]), unsafe_allow_html=True)

        evidence = message["evidence"]
        if evidence:
            cited = extract_cited_source_numbers(message["answer"])
            label = f"Sources ({len(cited)} cited, {len(evidence)} retrieved)" if cited else f"Sources ({len(evidence)})"
            with st.expander(label):
                st.markdown(render_source_chips([e["label"] for e in evidence]), unsafe_allow_html=True)
                st.markdown(
                    render_evidence_panel(evidence, max_excerpt_length=700, cited_indices=cited),
                    unsafe_allow_html=True,
                )

        rated = st.session_state.rated.get(message["id"])
        if rated:
            st.caption("Thanks, your feedback was recorded.")
        else:
            col_up, col_down, _ = st.columns([0.2, 0.26, 0.54])
            col_up.button("Helpful", key=f"up_{message['id']}", on_click=rate_answer, args=(message["id"], "up"))
            col_down.button("Not helpful", key=f"down_{message['id']}", on_click=rate_answer, args=(message["id"], "down"))


for existing in st.session_state.messages:
    render_exchange(existing)

if st.session_state.pop("feedback_error", False):
    st.warning("Your feedback could not be saved right now.")

can_ask = active_retriever is not None and generator is not None
typed = st.chat_input("Ask a question about the documents", disabled=not can_ask, max_chars=config.MAX_QUESTION_CHARS)
question = typed or st.session_state.pop("pending_question", None)

# Empty state: invite a first question (hidden as soon as one is being answered).
if not st.session_state.messages and not question and can_ask:
    st.markdown(
        '<div class="cw-lede">Every answer comes only from the documents, and shows the passage it was taken from. '
        "Start with a question of your own, or try one of these.</div>",
        unsafe_allow_html=True,
    )
    if mode == SAMPLE_MODE:
        columns = st.columns(2)
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            columns[index % 2].button(example, key=f"example_{index}", on_click=ask_example, args=(example,), use_container_width=True)

if question and can_ask:
    question = question.strip()
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
        new_message = {
            "id": uuid.uuid4().hex[:12],
            "question": question,
            "answer": generated.answer,
            "evidence": [{"label": lbl, "text": r.chunk.text} for lbl, r in zip(generated.sources_used, results)],
            "mode": mode,
            "top_k": top_k,
        }
        st.session_state.messages.append(new_message)
        render_exchange(new_message)
