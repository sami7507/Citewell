"""Tests for the optional sign-in helpers, the new settings, and the evidence/privacy wording."""

from citewell import config
from frontend.auth import configured_providers, display_name, provider_label, _mask_phone
from frontend.components import (
    _tidy_excerpt,
    render_evidence_panel,
    render_info_sections,
    render_welcome_brand,
    render_welcome_fineprint,
    render_welcome_heading,
)


# --- provider discovery ---

def test_configured_providers_lists_only_tables_with_a_client_id():
    auth = {
        "redirect_uri": "https://example.test/oauth2callback",
        "cookie_secret": "x",
        "google": {"client_id": "a", "client_secret": "b", "server_metadata_url": "u"},
        "phone": {"client_id": "c", "client_secret": "d", "server_metadata_url": "u"},
        "notes": {"hello": "world"},
    }
    assert configured_providers(auth) == ["google", "phone"]


def test_configured_providers_puts_google_first_then_phone_then_others():
    auth = {n: {"client_id": "x"} for n in ("zeta", "phone", "alpha", "google")}
    assert configured_providers(auth) == ["google", "phone", "alpha", "zeta"]


def test_configured_providers_handles_missing_or_invalid_config():
    assert configured_providers({}) == []
    assert configured_providers(None) == []
    assert configured_providers("not a mapping") == []


def test_provider_labels_are_friendly():
    assert provider_label("google") == "Continue with Google"
    assert provider_label("phone") == "Continue with phone number"
    assert provider_label("my_provider") == "Continue with My Provider"


# --- display name never exposes a full email or phone number ---

def test_display_name_prefers_the_name_claim():
    assert display_name({"name": "Sami Khan", "email": "sami@example.com"}) == "Sami Khan"


def test_display_name_falls_back_to_the_email_local_part_only():
    assert display_name({"email": "sami@example.com"}) == "sami"


def test_display_name_masks_a_phone_number():
    assert display_name({"phone_number": "+91 98765 43210"}) == "phone ending 210"
    assert _mask_phone("12") == "phone user"


def test_display_name_has_a_safe_default():
    assert display_name({}) == "Signed-in user"


# --- settings ---

def test_login_settings_have_safe_defaults():
    assert config.REQUIRE_LOGIN is False
    assert config.MAX_QUESTIONS_SIGNED_IN >= config.MAX_QUESTIONS_PER_SESSION


def test_require_login_parses_true_values(monkeypatch):
    monkeypatch.setenv("REQUIRE_LOGIN", "true")
    config.reload_from_env()
    assert config.REQUIRE_LOGIN is True
    monkeypatch.setenv("REQUIRE_LOGIN", "nonsense")
    config.reload_from_env()
    assert config.REQUIRE_LOGIN is False


# --- privacy wording follows the sign-in setup ---

def test_privacy_text_says_no_accounts_when_sign_in_is_off():
    assert "no accounts and no sign-in" in render_info_sections()


def test_privacy_text_describes_optional_and_required_sign_in():
    optional = render_info_sections(login_enabled=True)
    required = render_info_sections(login_enabled=True, login_required=True)
    assert "optional" in optional and "does not store your name" in optional
    assert "required" in required and "no accounts" not in required


# --- evidence text shows as readable sentences ---

def test_tidy_excerpt_joins_pdf_line_breaks_but_keeps_tables():
    assert _tidy_excerpt("A late fee\nof $75.00 applies.") == "A late fee of $75.00 applies."
    table = "Table 1 (page 1): includes: Net revenue.\n| a | b |\n|---|---|\n| 1 | 2 |"
    assert _tidy_excerpt(table) == table


def test_evidence_panel_no_longer_shows_mid_sentence_line_breaks():
    html = render_evidence_panel([{"label": "Source 1: l.pdf, page 1", "text": "Rent is due\non the 1st."}])
    assert "Rent is due on the 1st." in html


# --- the sign-in (welcome) page ---

def test_welcome_brand_panel_has_the_logo_promise_and_credit_in_single_line_html():
    html = render_welcome_brand()
    assert "Citewell" in html and "Answers you can check." in html and "A portfolio project by Sami" in html
    assert "<svg" in html and "\n" not in html


def test_welcome_heading_changes_when_sign_in_is_required():
    assert "look around as a guest" in render_welcome_heading(required=False)
    required = render_welcome_heading(required=True)
    assert "Sign in to continue." in required and "guest" not in required


def test_welcome_fineprint_states_what_is_not_stored():
    assert "does not store your name, email or phone number" in render_welcome_fineprint()


def test_theme_defines_the_welcome_layout_and_google_button_with_no_leftover_placeholder():
    from frontend.theme import CUSTOM_CSS
    assert "__GOOGLE_G__" not in CUSTOM_CSS
    assert ".st-key-welcome_google" in CUSTOM_CSS and "cw-welcome-brand" in CUSTOM_CSS
    assert "data:image/svg+xml,%3Csvg" in CUSTOM_CSS


# --- ask-row paperclip, tab title, footer colour, hamburger icon ---

def test_theme_replaces_the_sidebar_arrow_with_a_hamburger_icon():
    from frontend.theme import CUSTOM_CSS
    assert "__HAMBURGER__" not in CUSTOM_CSS
    assert "stSidebarCollapseButton" in CUSTOM_CSS and "stExpandSidebarButton" in CUSTOM_CSS
    assert "M4%206h16M4%2012h16M4%2018h16" in CUSTOM_CSS  # the three lines


def test_theme_styles_the_attach_button_and_uses_the_new_footer_colour():
    from frontend.theme import CUSTOM_CSS
    assert ".st-key-attach_wrap" in CUSTOM_CSS
    assert "--deep: #0B4A50" in CUSTOM_CSS and "background: var(--deep);" in CUSTOM_CSS
    assert "#14201C;\n  color: #C6D1CC" not in CUSTOM_CSS  # old near-black footer is gone


def test_browser_tab_title_is_just_the_product_name():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent / "frontend" / "app.py").read_text()
    assert 'page_title="Citewell"' in source
