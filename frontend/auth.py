"""
Optional sign-in for Citewell, built on Streamlit's own OpenID Connect support.

Why this design:
  * No passwords and no custom security code. Identity is verified by the provider
    (Google, or any OIDC provider that offers phone sign-in) and Streamlit keeps the session.
  * Citewell stores nothing about the user. The name is read from the session only to
    greet the person; it is never written to the database or logs.
  * Providers are discovered from the [auth.<name>] tables in the Streamlit secrets, so
    adding a provider is a configuration change, not a code change.

Phone-number sign-in needs an identity provider that sends SMS one-time codes (for example
Auth0, Firebase or Clerk configured for SMS). Configure it as an OIDC provider named
"phone" and its button appears automatically. Citewell deliberately does not implement
its own SMS codes: that needs a paid SMS gateway, carrier registration in many countries
(for example DLT in India), and careful abuse protection.

The helper functions at the top are plain Python (no Streamlit import) so they can be
unit tested; the functions below them import Streamlit lazily.
"""

import html
import importlib.util
import logging
from collections.abc import Mapping
from typing import List

from citewell import config
from citewell.services.secrets import secrets_file_exists

logger = logging.getLogger(__name__)

_LABELS = {"google": "Continue with Google", "phone": "Continue with phone number"}


def provider_label(name: str) -> str:
    """Button text for a provider name, e.g. 'google' -> 'Continue with Google'."""
    return _LABELS.get(name.lower(), f"Continue with {name.replace('_', ' ').title()}")


def configured_providers(auth_config) -> List[str]:
    """
    Provider names found in an [auth] secrets table: every sub-table that has a client_id.
    Google is listed first, then phone, then anything else alphabetically.
    """
    try:
        items = dict(auth_config).items()
    except Exception:
        return []
    names = [str(key) for key, value in items if isinstance(value, Mapping) and "client_id" in value]
    return sorted(names, key=lambda n: (n.lower() != "google", n.lower() != "phone", n.lower()))


def _mask_phone(number: str) -> str:
    digits = "".join(ch for ch in number if ch.isdigit())
    return f"phone ending {digits[-3:]}" if len(digits) >= 3 else "phone user"


def display_name(user) -> str:
    """A friendly, privacy-conscious name for the signed-in person (never the full email or phone)."""

    def get(key: str) -> str:
        try:
            value = user.get(key)
        except Exception:
            value = getattr(user, key, None)
        return str(value).strip() if value else ""

    name = get("name") or get("given_name") or get("preferred_username")
    if name:
        return name
    email = get("email")
    if email:
        return email.split("@")[0]
    phone = get("phone_number")
    return _mask_phone(phone) if phone else "Signed-in user"


# ---------------------------------------------------------------- Streamlit-dependent helpers

def _on_streamlit_cloud() -> bool:
    return str(config.PROJECT_ROOT).startswith("/mount/src")


def available_providers() -> List[str]:
    """Providers that are configured AND usable in this environment (empty list hides sign-in)."""
    import streamlit as st

    if not hasattr(st, "login") or not hasattr(st, "user"):
        return []  # Streamlit older than 1.42
    if importlib.util.find_spec("authlib") is None:
        logger.info("Sign-in is hidden because the Authlib package is not installed.")
        return []
    # Reading st.secrets with no secrets file makes Streamlit complain, so only read it when
    # a file exists (local) or when running on Streamlit Community Cloud.
    if not (secrets_file_exists() or _on_streamlit_cloud()):
        return []
    try:
        return configured_providers(st.secrets.get("auth", {}))
    except Exception:
        return []


def is_logged_in() -> bool:
    import streamlit as st

    return bool(getattr(getattr(st, "user", None), "is_logged_in", False))


def current_user_name() -> str:
    import streamlit as st

    return display_name(st.user)


def login_buttons(providers: List[str], key_prefix: str) -> None:
    """One full-width button per provider; clicking starts that provider's sign-in."""
    import streamlit as st

    for name in providers:
        if st.button(provider_label(name), key=f"{key_prefix}_{name}", use_container_width=True):
            try:
                st.login(name)
            except Exception:
                logger.exception("Sign-in could not start for provider %s", name)
                st.error("Sign-in is not set up correctly yet. See the app logs for details.")


def render_account_panel(providers: List[str], is_guest: bool = False) -> None:
    """
    Sidebar block. Signed in: the name and a Sign out button. Guest: a note and a Sign in button
    that returns to the welcome page. (The sign-in options themselves live on the welcome page.)
    """
    import streamlit as st

    st.markdown('<div class="cw-side-label">Account</div>', unsafe_allow_html=True)
    if is_logged_in():
        name = html.escape(current_user_name())
        st.markdown(
            f'<div class="cw-account"><div class="cw-account-name">{name}</div>'
            '<div class="cw-account-note">Signed in</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Sign out", key="logout", use_container_width=True):
            st.session_state.pop("guest", None)
            st.logout()
    else:
        st.markdown(
            '<div class="cw-account"><div class="cw-account-name">Guest</div>'
            '<div class="cw-account-note">Signing in raises your question limit</div></div>',
            unsafe_allow_html=True,
        )
        if providers:
            st.button("Sign in", key="sidebar_signin", on_click=lambda: st.session_state.pop("guest", None), use_container_width=True)
