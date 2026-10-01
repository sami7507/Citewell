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

.block-container { max-width: 52rem; padding-top: 2.2rem; padding-bottom: 6rem; }

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

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
@media (max-width: 640px) { .cw-title { font-size: 1.7rem; } .block-container { padding-top: 1.2rem; } }
"""
