"""Bridge Streamlit secrets into environment variables (no Streamlit import here)."""

import os
from pathlib import Path
from typing import Tuple

from citewell import config

DEFAULT_KEYS = ("GROQ_API_KEY", "GROQ_MODEL", "EMBEDDING_MODEL", "TOP_K", "UPLOAD_TOP_K")


def secrets_file_exists() -> bool:
    """
    Check whether a Streamlit secrets.toml exists WITHOUT touching st.secrets.

    Merely accessing st.secrets when no file exists makes Streamlit render a
    visible "No secrets found" box, which is noise during local development
    (where configuration comes from .env). Deployed apps always have the file.
    """
    candidates = [
        Path.home() / ".streamlit" / "secrets.toml",
        config.PROJECT_ROOT / ".streamlit" / "secrets.toml",
    ]
    return any(p.exists() for p in candidates)


def bridge_secrets_to_env(secrets, keys: Tuple[str, ...] = DEFAULT_KEYS) -> None:
    """
    Copy selected keys from a secrets-like mapping into os.environ, then
    re-read the config so local (.env) and deployed (secrets.toml) setups
    behave identically. Accepts any mapping, so it is testable with a dict.
    """
    for key in keys:
        try:
            if key in secrets:
                os.environ[key] = str(secrets[key])
        except Exception:
            pass  # some secrets objects raise when unconfigured; safe to ignore
    config.reload_from_env()
