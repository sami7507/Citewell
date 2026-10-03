"""
The sign-in (welcome) page: the first screen when sign-in is configured.

Left third: branding. Right two thirds: the sign-in options, plus an optional guest entry.
Layout lives in frontend/theme.py; the HTML pieces come from frontend/components.py.
"""

from typing import Callable, List

from frontend.auth import login_buttons
from frontend.components import render_welcome_brand, render_welcome_fineprint, render_welcome_heading


def render_welcome(providers: List[str], allow_guest: bool, on_guest: Callable[[], None]) -> None:
    import streamlit as st

    left, right = st.columns([1, 2], gap="small")

    with left:
        st.markdown(render_welcome_brand(), unsafe_allow_html=True)

    with right:
        _, middle, _ = st.columns([1, 5, 1])
        with middle:
            st.markdown(render_welcome_heading(required=not allow_guest), unsafe_allow_html=True)
            if providers:
                login_buttons(providers, "welcome")
            else:
                st.error("Sign-in is required for this deployment, but it has not been set up yet.")
            if allow_guest:
                st.markdown('<div class="cw-or"><span>or</span></div>', unsafe_allow_html=True)
                st.button("Continue as guest", key="welcome_guest", on_click=on_guest, use_container_width=True)
            st.markdown(render_welcome_fineprint(), unsafe_allow_html=True)
