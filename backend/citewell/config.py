"""
Central configuration for Citewell.

Every tunable decision in the system (models, chunking, retrieval, limits,
storage locations) lives here and is read from environment variables, or
from a `.env` file in the project root. Nothing sensitive is hard-coded,
and swapping a model or a path never requires touching pipeline logic.

Settings that depend on environment variables are re-read by
`reload_from_env()`, which the app calls after bridging Streamlit secrets
into the environment (see citewell.services.secrets).
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/citewell/config.py -> project root is three levels up from this file.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# A local .env is optional. In deployment, real environment variables or
# Streamlit secrets are used instead, which makes this a safe no-op there.
load_dotenv(PROJECT_ROOT / ".env")


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Parse an integer setting, falling back to the default on bad input."""
    try:
        return max(minimum, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_path(name: str, default: str) -> Path:
    """Resolve a path setting; relative paths are relative to the project root."""
    path = Path(_env_str(name, default)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _read_settings() -> dict:
    return {
        # --- LLM (Groq) ---
        "GROQ_API_KEY": _env_str("GROQ_API_KEY", ""),
        "GROQ_MODEL": _env_str("GROQ_MODEL", "openai/gpt-oss-120b"),
        # Optional backup, tried once if the main model fails (error, empty answer, or its own
        # rate limit). Groq limits each model separately, so a second model often still has quota.
        # Empty (the default) disables it: only set a model id your Groq account can actually use.
        "GROQ_FALLBACK_MODEL": os.getenv("GROQ_FALLBACK_MODEL", "").strip(),
        "LLM_TIMEOUT_SECONDS": _env_int("LLM_TIMEOUT_SECONDS", 60),
        "LLM_MAX_RETRIES": _env_int("LLM_MAX_RETRIES", 3),
        # --- Embeddings (local, free) ---
        "EMBEDDING_MODEL": _env_str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        # --- Chunking ---
        "CHUNK_SIZE": _env_int("CHUNK_SIZE", 800),
        "CHUNK_OVERLAP": _env_int("CHUNK_OVERLAP", 120, minimum=0),
        # --- Retrieval ---
        # TOP_K=2 was chosen empirically: Recall@k and MRR plateau at k=2 on the
        # labelled demo corpus (see the evaluation section of the README), while
        # precision keeps falling as k grows. It is only validated for that small,
        # curated corpus, so uploads get a more generous default.
        "TOP_K": _env_int("TOP_K", 2),
        "UPLOAD_TOP_K": _env_int("UPLOAD_TOP_K", 4),
        # Minimum cosine similarity for a chunk to be kept in upload mode only.
        # Deliberately permissive: a safety net against padding, not a tuned filter.
        "MIN_RELEVANCE_SCORE": _env_float("MIN_RELEVANCE_SCORE", 0.15),
        # --- Limits (protect shared, free-tier deployments) ---
        "MAX_QUESTION_CHARS": _env_int("MAX_QUESTION_CHARS", 1000),
        "MAX_UPLOAD_FILES": _env_int("MAX_UPLOAD_FILES", 5),
        "MAX_UPLOAD_MB": _env_int("MAX_UPLOAD_MB", 50),
        "MAX_PDF_PAGES": _env_int("MAX_PDF_PAGES", 600),
        "MAX_CONTEXT_CHARS_PER_CHUNK": _env_int("MAX_CONTEXT_CHARS_PER_CHUNK", 6000),
        "MAX_CONTEXT_CHARS_TOTAL": _env_int("MAX_CONTEXT_CHARS_TOTAL", 14000),
        # Questions one browser session may ask using the server's shared key (protects a free quota).
        # Visitors who paste their own key are not limited.
        "MAX_QUESTIONS_PER_SESSION": _env_int("MAX_QUESTIONS_PER_SESSION", 30, minimum=0),  # 0 = unlimited
        # Signed-in visitors get a higher cap. A cap is per browser session, not a per-account quota.
        "MAX_QUESTIONS_SIGNED_IN": _env_int("MAX_QUESTIONS_SIGNED_IN", 100, minimum=0),
        # When true, visitors must sign in before asking anything (needs sign-in to be configured).
        "REQUIRE_LOGIN": _env_bool("REQUIRE_LOGIN", False),
        # --- Logging ---
        "LOG_LEVEL": _env_str("LOG_LEVEL", "INFO").upper(),
    }


# Expose every setting as a module attribute (config.TOP_K, config.GROQ_MODEL, ...).
globals().update(_read_settings())


def reload_from_env() -> None:
    """Re-read environment-dependent settings (e.g. after secrets are bridged)."""
    globals().update(_read_settings())


# --- Storage locations (relative paths resolve against the project root) ---
STORAGE_DIR = _env_path("STORAGE_DIR", "storage")
SAMPLE_DOCS_DIR = _env_path("SAMPLE_DOCS_DIR", "storage/sample_docs")
VECTORSTORE_DIR = _env_path("VECTORSTORE_DIR", "storage/index")
DATABASE_PATH = _env_path("DATABASE_PATH", "storage/citewell.db")
EVAL_RESULTS_DIR = _env_path("EVAL_RESULTS_DIR", "storage/eval_results")


def ensure_dirs() -> None:
    """Create storage directories if they do not exist yet. Safe to call repeatedly."""
    for directory in (STORAGE_DIR, SAMPLE_DOCS_DIR, VECTORSTORE_DIR, EVAL_RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    """Configure process-wide logging once; later calls are no-ops."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),  # noqa: F821 (set via globals)
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
