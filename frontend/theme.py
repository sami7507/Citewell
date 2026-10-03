"""
Visual identity for Citewell.

The idea: a printed page, read with a highlighter. The interface is a quiet,
cool-grey desk with white sheets of text; the single bright colour is marker
yellow, used only where the app points at evidence (citation marks, the
"used in answer" passages, the wordmark underline). Deep teal handles actions.

Answers and quoted passages are set in a text serif, as a document would be;
the surrounding interface uses a clean sans.

Streamlit's own theme (see .streamlit/config.toml) controls its native widgets.
Custom CSS here is limited to what that theme cannot express, and every custom
element sets its background and text colour together.
"""

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap');

:root {
  --paper: #F2F4F1;
  --sheet: #FFFFFF;
  --ink: #14201C;
  --deep: #0B4A50;
  --deep-bar: #0F5E66;
  --deep-line: #1E6A71;
  --deep-text: #D3E6E7;
  --deep-muted: #9CC2C5;
  --muted: #5B6862;
  --line: #D6DDD9;
  --teal: #0D5C63;
  --teal-soft: #E3EFEF;
  --mark: #FFE066;
  --mark-soft: rgba(255, 224, 102, 0.40);
  --serif: 'Source Serif 4', Georgia, 'Times New Roman', serif;
  --sans: 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}

.stApp, .stMarkdown, button, input, textarea, label,
[data-testid="stSidebar"] { font-family: var(--sans); }

/* Keep Streamlit's header (it holds the sidebar toggle) but make it blend in. */
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

.block-container { max-width: 100% !important; padding: 2.2rem 0 0 0 !important; }

/* ---------- Wordmark: the title carries a marker swipe ---------- */
.cw-wordmark { margin: 0.2rem 0 0.2rem 0; }
.cw-wordmark span {
  font-family: var(--serif);
  font-size: 1.7rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--ink);
  background: linear-gradient(transparent 62%, var(--mark) 62%, var(--mark) 92%, transparent 92%);
  padding: 0 0.12em;
}
.cw-tagline { color: var(--muted); font-size: 0.9rem; margin: 0.3rem 0 0.4rem 0; }

/* ---------- Page heading and empty state ---------- */
.cw-title {
  font-family: var(--serif);
  font-size: 2.1rem;
  font-weight: 600;
  line-height: 1.2;
  color: var(--ink);
  margin: 0.4rem 0 0.5rem 0;
}
.cw-lede { color: var(--muted); font-size: 1.02rem; line-height: 1.55; max-width: 38rem; margin-bottom: 1.4rem; }
.cw-status { color: var(--muted); font-size: 0.88rem; margin-bottom: 1.2rem; }

/* ---------- Conversation ---------- */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] { display: none; }

[data-testid="stChatMessage"] {
  background: transparent;
  padding: 0.2rem 0 !important;
  gap: 0 !important;
}
/* The question reads as a heading; the answer sits on a white sheet. */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {
  font-family: var(--serif);
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--ink);
  margin-top: 1.4rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) > div:last-child {
  background: var(--sheet);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 1rem 1.2rem 0.4rem 1.2rem;
}
[data-testid="stChatMessage"] .stMarkdown p,
[data-testid="stChatMessage"] .stMarkdown li {
  font-family: var(--serif);
  font-size: 1.04rem;
  line-height: 1.65;
  color: var(--ink);
}

/* Citation marks inside an answer */
sup.cw-ref {
  font-family: var(--sans);
  font-size: 0.68rem;
  font-weight: 600;
  color: var(--ink);
  background: var(--mark);
  border-radius: 3px;
  padding: 0 0.28em;
  margin: 0 0.12em;
  vertical-align: super;
  line-height: 1;
}

/* ---------- Sources and evidence ---------- */
.source-chip {
  display: inline-block;
  font-family: var(--sans);
  font-size: 0.8rem;
  color: var(--ink);
  background: var(--teal-soft);
  border: 1px solid #BCD6D7;
  border-radius: 4px;
  padding: 3px 9px;
  margin: 3px 6px 3px 0;
}
.evidence-block {
  background: var(--sheet);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 0.65rem 0.9rem;
  margin: 0.55rem 0;
}
.evidence-block .evidence-text {
  font-family: var(--serif);
  font-size: 0.95rem;
  line-height: 1.55;
  color: var(--ink);
  white-space: pre-wrap;
  background: linear-gradient(var(--mark-soft), var(--mark-soft));
  box-decoration-break: clone;
  padding: 0.1rem 0.25rem;
  border-radius: 2px;
}
.evidence-block.unused { background: var(--paper); }
.evidence-block.unused .evidence-text { background: none; color: var(--muted); }
.evidence-label { font-family: var(--sans); font-size: 0.8rem; font-weight: 600; color: var(--ink); margin-bottom: 0.35rem; }
.evidence-block.unused .evidence-label { color: var(--muted); font-weight: 500; }
.evidence-used-badge { font-weight: 500; color: var(--teal); margin-left: 0.6rem; }
.evidence-section-label { font-size: 0.82rem; color: var(--muted); margin: 0.9rem 0 0.2rem 0; }

[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 8px; background: var(--sheet); }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
.cw-doc-list { font-size: 0.88rem; color: var(--ink); line-height: 1.7; margin: 0.2rem 0 0.4rem 0; }
.cw-doc-list div { padding: 0.05rem 0; }

/* ---------- Inputs and buttons ---------- */
.stButton > button {
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--sheet);
  color: var(--ink);
  font-weight: 500;
  text-align: left;
}
.stButton > button:hover { border-color: var(--teal); color: var(--teal); background: var(--sheet); }
.stButton > button:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }

/* ---------- Sidebar account and labels ---------- */
.cw-side-label { font-weight: 600; font-size: 0.85rem; color: var(--ink); margin: 0.9rem 0 0.35rem 0; }
.cw-account { background: var(--sheet); border: 1px solid var(--line); border-radius: 10px; padding: 0.6rem 0.8rem; margin-bottom: 0.5rem; }
.cw-account-name { font-weight: 600; font-size: 0.95rem; color: var(--ink); }
.cw-account-note { font-size: 0.8rem; color: var(--muted); }
.cw-sources-title { font-size: 0.85rem; font-weight: 600; color: var(--muted); margin: 0.9rem 0 0.1rem 0; }

/* ---------- Ask box ---------- */
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stTextInput"] [data-baseweb="base-input"] { background: var(--sheet); border-radius: 10px; }
[data-testid="stTextInput"] input { font-size: 1.02rem; padding-top: 0.75rem; padding-bottom: 0.75rem; }
.cw-try { font-size: 0.85rem; color: var(--muted); margin: 0.4rem 0 0.2rem 0; }

/* ---------- Info sections (a separate band below the app) ---------- */
.cw-info { margin-top: 3.2rem; padding-top: 0.4rem; border-top: 1px solid var(--line); }
.cw-section { margin: 2.2rem 0 0 0; }
.cw-section-title { font-family: var(--serif); font-size: 1.35rem; font-weight: 600; color: var(--ink); margin-bottom: 0.8rem; }
.cw-cards { display: grid; gap: 0.8rem; }
.cw-cards-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.cw-cards-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.cw-card, .cw-note {
  background: var(--sheet);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  color: var(--ink);
}
.cw-card-title { font-weight: 600; font-size: 0.95rem; color: var(--ink); margin-bottom: 0.25rem; }
.cw-card-body { font-size: 0.88rem; line-height: 1.5; color: var(--muted); }
.cw-step {
  display: inline-block; min-width: 1.5rem; text-align: center;
  font-family: var(--serif); font-weight: 600; font-size: 0.95rem;
  color: var(--ink); background: var(--mark); border-radius: 4px; padding: 0 0.3rem; margin-bottom: 0.45rem;
}
.cw-note ul { margin: 0.3rem 0 0 0; padding-left: 1.1rem; }
.cw-note li { font-size: 0.88rem; line-height: 1.5; color: var(--muted); margin-bottom: 0.25rem; }

/* ---------- Site footer: full width, dark, pinned to the bottom of the page ---------- */
/* Make the page at least one screen tall and push the footer to the bottom of it. */
.block-container { min-height: 100vh; display: flex; flex-direction: column; }
.block-container > [data-testid="stVerticalBlock"] { flex: 1 1 auto; width: 100%; }
/* Centre everything except the footer in a readable column. */
.block-container > [data-testid="stVerticalBlock"] > *:not(:has(.cw-footer-full)):not(:has(.cw-welcome-brand)) {
  max-width: 52rem; width: 100%; margin-left: auto; margin-right: auto;
  padding-left: 1.5rem; padding-right: 1.5rem; box-sizing: border-box;
}
.element-container:has(.cw-footer-full),
[data-testid="stElementContainer"]:has(.cw-footer-full) { margin-top: auto; }

.cw-footer-full {
  margin: 3.5rem 0 0 0;
  background: var(--deep);
  color: var(--deep-text);
}
.cw-top {
  display: block; text-align: center; padding: 0.9rem 1rem;
  background: var(--deep-bar); color: #FFFFFF !important;
  font-size: 0.88rem; text-decoration: none !important;
}
.cw-top:hover { background: #13707A; }
.cw-footer-inner { max-width: 64rem; margin: 0 auto; padding: 2.8rem 1.5rem 0 1.5rem; }
.cw-footer-grid { display: grid; grid-template-columns: 1.6fr 1fr 1fr 1fr; gap: 2rem; }
.cw-footer-brand span { font-family: var(--serif); font-size: 1.55rem; font-weight: 600; color: #FFFFFF; }
.cw-footer-brand span::after { content: ""; display: block; width: 2.4rem; height: 3px; margin-top: 6px; background: var(--mark); }
.cw-footer-about p { font-size: 0.9rem; line-height: 1.6; color: var(--deep-muted); margin: 0.9rem 0 0 0; max-width: 20rem; }
.cw-footer-head { font-weight: 600; font-size: 0.95rem; color: #FFFFFF; margin-bottom: 0.7rem; }
.cw-footer-col a {
  display: block; padding: 0.2rem 0; font-size: 0.9rem;
  color: var(--deep-text) !important; text-decoration: none !important;
}
.cw-footer-col a:hover {
  color: #FFFFFF !important; text-decoration: underline !important;
  text-decoration-color: var(--mark) !important; text-underline-offset: 4px;
}
.cw-footer-bar {
  margin-top: 2.4rem; padding: 1.2rem 0 1.8rem 0; border-top: 1px solid var(--deep-line);
  font-size: 0.8rem; line-height: 1.55; color: var(--deep-muted);
}
@media (max-width: 760px) {
  .cw-footer-grid { grid-template-columns: 1fr 1fr; }
  .cw-footer-about { grid-column: 1 / -1; }
}

/* Polish: sources panel sits quietly inside the answer sheet; tighter sidebar top */
[data-testid="stChatMessage"] [data-testid="stExpander"] { border: none; background: var(--paper); border-radius: 8px; }
[data-testid="stSidebarUserContent"] { padding-top: 0.4rem; }

@media (max-width: 760px) {
  .cw-cards-3, .cw-cards-2 { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (max-width: 640px) { .cw-title { font-size: 1.7rem; } .block-container { padding-top: 1.2rem !important; } }
"""


_GOOGLE_G = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'>"
    "<path fill='#EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/>"
    "<path fill='#4285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/>"
    "<path fill='#FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z'/>"
    "<path fill='#34A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z'/>"
    "</svg>"
)

WELCOME_CSS = """
/* ---------- Sign-in (welcome) page: brand panel on the left third, options on the right ---------- */
.block-container:has(.cw-welcome-brand) { padding-top: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.cw-welcome-brand) { gap: 0 !important; align-items: stretch; }
[data-testid="stColumn"]:has(.cw-welcome-brand), [data-testid="column"]:has(.cw-welcome-brand) {
  background: var(--deep); min-height: 100vh;
}
.cw-welcome-brand {
  min-height: 100vh; box-sizing: border-box; padding: 3.2rem 2.4rem 2.2rem 2.4rem;
  display: flex; flex-direction: column; justify-content: space-between; gap: 2rem; color: var(--deep-text);
}
.cw-welcome-logo span { font-family: var(--serif); font-size: 2.7rem; font-weight: 600; color: #FFFFFF; letter-spacing: -0.01em; }
.cw-welcome-logo span::after { content: ""; display: block; width: 3rem; height: 4px; margin-top: 8px; background: var(--mark); }
.cw-welcome-promise { font-family: var(--serif); font-size: 1.55rem; font-weight: 600; line-height: 1.3; color: #FFFFFF; margin-top: 2.4rem; }
.cw-welcome-sub { font-size: 0.98rem; line-height: 1.6; color: var(--deep-muted); margin: 0.8rem 0 0 0; max-width: 22rem; }
.cw-welcome-points { list-style: none; margin: 1.6rem 0 0 0; padding: 0; }
.cw-welcome-points li { display: flex; gap: 0.7rem; align-items: baseline; font-size: 0.93rem; line-height: 1.5; color: #E6F1F2; margin-bottom: 0.65rem; }
.cw-welcome-dot { flex: 0 0 auto; width: 0.55rem; height: 0.55rem; background: var(--mark); border-radius: 2px; transform: translateY(-1px); }
.cw-welcome-art { max-width: 17rem; opacity: 0.95; }
.cw-welcome-sheet { width: 100%; height: auto; display: block; }
.cw-welcome-credit { font-size: 0.82rem; color: var(--deep-muted); }

.cw-welcome-right-space { height: 17vh; }
.cw-welcome-title { font-family: var(--serif); font-size: 2.1rem; font-weight: 600; line-height: 1.2; color: var(--ink); }
.cw-welcome-lede { font-size: 1rem; line-height: 1.55; color: var(--muted); margin: 0.6rem 0 1.8rem 0; }
.cw-or { display: flex; align-items: center; gap: 0.8rem; margin: 1.1rem 0 0.9rem 0; color: var(--muted); font-size: 0.85rem; }
.cw-or::before, .cw-or::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.cw-welcome-fine { font-size: 0.82rem; line-height: 1.5; color: var(--muted); margin-top: 1.6rem; }

/* Sign-in buttons */
[class*="st-key-welcome_"] button { height: 3.1rem; border-radius: 10px; font-size: 0.98rem; font-weight: 500; }
.st-key-welcome_google button {
  background-color: #FFFFFF; border: 1px solid #C9D2CE; color: var(--ink);
  background-image: url("data:image/svg+xml,__GOOGLE_G__");
  background-repeat: no-repeat; background-position: 1.1rem center; background-size: 1.15rem;
}
.st-key-welcome_google button:hover { border-color: var(--teal); box-shadow: 0 1px 4px rgba(20, 32, 28, 0.12); }
.st-key-welcome_phone button { background: var(--teal); border: 1px solid var(--teal); color: #FFFFFF; }
.st-key-welcome_phone button:hover { background: #0A4A50; color: #FFFFFF; }
.st-key-welcome_guest button { background: transparent; border: none; color: var(--teal); text-decoration: underline; text-underline-offset: 4px; }
.st-key-welcome_guest button:hover { background: transparent; color: #0A4A50; }

@media (max-width: 760px) {
  [data-testid="stColumn"]:has(.cw-welcome-brand), [data-testid="column"]:has(.cw-welcome-brand), .cw-welcome-brand { min-height: auto; }
  .cw-welcome-right-space { height: 2rem; }
  .cw-welcome-art { display: none; }
}
""".replace("__GOOGLE_G__", __import__("urllib.parse", fromlist=["quote"]).quote(_GOOGLE_G, safe="/:=,'"))

CUSTOM_CSS = CUSTOM_CSS + WELCOME_CSS


EXTRA_CSS = """
/* ---------- Sidebar open/close control: the familiar three-line (hamburger) icon ---------- */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stExpandSidebarButton"] button,
button[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] button {
  width: 2.5rem; height: 2.5rem; border-radius: 8px;
  font-size: 0 !important; color: transparent !important;       /* hides the original arrow glyph */
  background-color: transparent;
  background-image: url("data:image/svg+xml,__HAMBURGER__");
  background-repeat: no-repeat; background-position: center; background-size: 1.35rem;
}
[data-testid="stSidebarCollapseButton"] button *,
[data-testid="stSidebarCollapsedControl"] button *,
[data-testid="stExpandSidebarButton"] button *,
button[data-testid="stExpandSidebarButton"] *,
[data-testid="collapsedControl"] button * { display: none !important; }
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stSidebarCollapsedControl"] button:hover,
[data-testid="stExpandSidebarButton"] button:hover,
button[data-testid="stExpandSidebarButton"]:hover,
[data-testid="collapsedControl"] button:hover { background-color: rgba(20, 32, 28, 0.08); }

/* ---------- Attach (paperclip) button at the right end of the ask row ---------- */
.st-key-attach_wrap button { height: 2.75rem; border-radius: 10px; border: 1px solid var(--line); background: var(--sheet); color: var(--ink); }
.st-key-attach_wrap button:hover { border-color: var(--teal); color: var(--teal); }
/* Icon only: hide everything Streamlit puts inside the button (label, its own icon and the dropdown arrow)
   and draw one paperclip instead. Clicking still opens the upload panel. */
.st-key-attach_wrap button {
  font-size: 0 !important; color: transparent !important;
  background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2024%2024'%20fill='none'%20stroke='%2314201C'%20stroke-width='2'%20stroke-linecap='round'%20stroke-linejoin='round'%3E%3Cpath%20d='M21.44%2011.05l-9.19%209.19a6%206%200%200%201-8.49-8.49l9.19-9.19a4%204%200%200%201%205.66%205.66l-9.2%209.19a2%202%200%200%201-2.83-2.83l8.49-8.48'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: center; background-size: 1.25rem;
}
.st-key-attach_wrap button * { display: none !important; }
.st-key-ask_button button { height: 2.75rem; }
"""

EXTRA_CSS = EXTRA_CSS.replace("__HAMBURGER__", __import__("urllib.parse", fromlist=["quote"]).quote("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#14201C' stroke-width='2' stroke-linecap='round'><path d='M4 6h16M4 12h16M4 18h16'/></svg>", safe="/:=,'"))
CUSTOM_CSS = CUSTOM_CSS + EXTRA_CSS
