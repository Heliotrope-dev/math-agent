"""CSS and JS strings for Math Agent UI."""

_BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
@import url('https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css');

:root {
    --bg:        #F8F8FA;
    --surface:   #FFFFFF;
    --sidebar:   #F2F3F5;
    --border:    #E4E6EA;
    --text:      #1A1A2E;
    --text-muted:#6E6E82;
    --accent:    #2563EB;
    --user-bg:   #2563EB;
    --user-text: #FFFFFF;
    --radius:    12px;
    --radius-sm: 8px;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.bubble-asst-inner { font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif; font-size: 1rem; line-height: 1.8; }

html, body { background: var(--bg) !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"],
footer { background: var(--bg) !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4 { color: var(--text) !important; }
#MainMenu, header { visibility: hidden; }
[data-testid="block-container"] { padding-bottom: 180px !important; }

header[data-testid="stHeader"] {
    background: var(--surface) !important;
    box-shadow: none !important;
    border-bottom: 1px solid var(--border) !important;
}
header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
.main .block-container { padding-top: 0.5rem !important; }

[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }
[data-testid="stSidebar"] .stButton button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-muted) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    padding: 6px 10px !important;
    height: auto !important; min-height: 32px !important;
    white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
    display: block !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    color: var(--accent) !important; border-color: var(--accent) !important;
}

.course-banner {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; margin-bottom: 12px;
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
    font-size: 0.9rem; font-weight: 600; color: var(--text-muted);
}
.app-header {
    display: flex; align-items: center; gap: 10px;
    padding: 0.5rem 0 1rem; border-bottom: 1px solid var(--border);
}
.app-header-title { font-size: 1rem; font-weight: 600; color: var(--text-muted) !important; }

.welcome-wrap { text-align: center; padding: 2.5rem 0 1.5rem; }
.welcome-title { font-size: 1.8rem; font-weight: 600; color: var(--text) !important; margin-bottom: 0.5rem; }
.welcome-sub { font-size: 0.88rem; color: var(--text-muted) !important; margin-bottom: 2rem; }
.greeting-wrap { text-align: center; padding: 4rem 0 2rem; }
.greeting-main { font-size: 2rem; font-weight: 600; color: var(--text) !important; margin-bottom: 0.4rem; }
.greeting-sub { font-size: 0.9rem; color: var(--text-muted) !important; }

[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-size: 0.85rem !important; padding: 12px 16px !important;
    text-align: left !important; line-height: 1.45 !important;
    min-height: 56px !important; height: auto !important; white-space: normal !important;
    box-shadow: none !important;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    border-color: var(--accent) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.1) !important;
}

.refresh-btn button {
    background: transparent !important; border: 1px solid var(--border) !important;
    border-radius: 20px !important; color: var(--text-muted) !important; font-size: 0.82rem !important;
}
.refresh-btn button:hover { border-color: var(--accent) !important; color: var(--accent) !important; }

.msg-row-user { display: flex; justify-content: flex-end; margin: 6px 0; }
.bubble-user {
    background: var(--user-bg) !important;
    color: var(--user-text) !important;
    border-radius: 18px 4px 18px 18px !important;
    padding: 10px 14px; word-break: break-word; line-height: 1.6;
    font-size: 0.95rem; display: inline-block; max-width: 72%;
}

.bubble-asst-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px 18px 18px 18px;
    padding: 10px 14px; word-break: break-word; line-height: 1.6; font-size: 0.95rem;
}
.bubble-asst-wrap p, .bubble-asst-wrap li { color: var(--text) !important; }
.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px 18px 18px 18px; padding: 10px 14px;
    font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif;
    font-size: 1rem; line-height: 1.8; word-break: break-word;
}

.guide-bar { display: flex; align-items: center; gap: 8px; padding: 2px 0 4px; }
.guide-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--sidebar); border: 1px solid var(--border); border-radius: 20px;
    padding: 4px 12px; font-size: 0.82rem; color: var(--text-muted);
    cursor: pointer; user-select: none; transition: all 0.15s;
}
.guide-chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }

.plus-panel {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 16px; padding: 16px 12px; margin: 8px 0;
}
.plus-panel .stButton button {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important; padding: 14px 6px !important;
    height: 76px !important; font-size: 0.82rem !important; color: var(--text-muted) !important;
    box-shadow: none !important;
}
.plus-panel .stButton button:hover {
    border-color: var(--accent) !important; color: var(--accent) !important;
}

.toolbar-btn button {
    background: transparent !important; border: none !important;
    font-size: 1.4rem !important; padding: 6px !important;
    border-radius: 50% !important; color: var(--text-muted) !important;
    height: 44px !important; width: 44px !important;
}
.toolbar-btn button:hover { background: var(--sidebar) !important; color: var(--text) !important; }

[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: var(--bg) !important; }
[data-testid="stChatInputContainer"] {
    background: var(--surface) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 24px !important;
    padding: 8px 14px !important; margin: 0 0 10px !important; box-shadow: none !important;
}
[data-testid="stChatInputContainer"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important; border: none !important;
    box-shadow: none !important; border-radius: 0 !important;
    color: var(--text) !important; font-size: 0.95rem !important; padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus { box-shadow: none !important; border: none !important; outline: none !important; }
[data-testid="stChatInputSubmitButton"] button { background: var(--accent) !important; border-radius: 50% !important; }

[data-testid="stHorizontalBlock"]:has(.toolbar-btn) {
    position: sticky !important; bottom: 72px !important; z-index: 200 !important;
    background: var(--bg) !important; padding: 4px 0 2px !important; margin: 0 !important;
}
.course-banner-row [data-testid="stHorizontalBlock"],
[data-testid="stHorizontalBlock"]:has(.course-banner) { align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.course-banner) [data-testid="stButton"] button {
    height: 100% !important; min-height: 42px !important;
}
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }
[data-testid="element-container"] { background: transparent !important; }

.toolbar-model [data-testid="stSelectbox"] > div > div {
    border: 1px solid var(--border) !important;
    background: rgba(255,255,255,0.9) !important;
    font-size: 0.82rem !important; color: var(--text) !important;
    padding: 4px 10px !important; min-height: 36px !important; border-radius: 20px !important;
}

[data-testid="stPills"] { margin-top: 8px !important; }
div[data-testid="stPills"] > div > label > div,
div[data-testid="stPills"] button,
div[data-testid="stPills"] [role="radio"],
div[data-testid="stPills"] [role="button"] {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 20px !important; color: var(--text-muted) !important;
    font-size: 0.78rem !important; padding: 3px 12px !important;
}
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-selected="true"],
div[data-testid="stPills"] [aria-checked="true"],
div[data-testid="stPills"] [aria-selected="true"] {
    background-color: var(--accent) !important;
    border-color: var(--accent) !important; color: #ffffff !important;
}
div[data-testid="stPills"] p,
div[data-testid="stPills"] span { color: inherit !important; background: transparent !important; }

.stButton button { border-radius: var(--radius-sm) !important; font-size: 0.84rem !important; }
.stButton button[kind="primary"] { background: var(--accent) !important; border: none !important; color: #fff !important; }
.stButton button[kind="primary"]:hover { background: #1d4ed8 !important; }

.turn-badge {
    display: inline-block; background: var(--sidebar); border: 1px solid var(--border);
    color: var(--text-muted); padding: 1px 8px; border-radius: 6px; font-size: 0.7rem; margin-bottom: 4px;
}
[data-testid="stExpander"] { border: 1px solid var(--border) !important; border-radius: 10px !important; background: var(--surface) !important; }
[data-testid="stStatusWidget"] { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }

pre, code { background: #F0F1F3 !important; border: 1px solid var(--border) !important; border-radius: 8px !important; font-size: 0.82rem !important; color: #333 !important; }
hr { border-color: var(--border) !important; }

.katex-display { margin: 0.8em 0 !important; overflow-x: auto !important; overflow-y: hidden !important; }
.katex { font-size: 1.05em !important; }
.katex-display > .katex { font-size: 1.1em !important; }

[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
[data-testid="stAudioInput"] button { background: transparent !important; color: var(--text-muted) !important; width: 72px !important; height: 72px !important; min-width: 72px !important; border-radius: 50% !important; }
[data-testid="stAudioInput"] button svg { width: 36px !important; height: 36px !important; }

[data-testid="stTextArea"] textarea {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: 16px !important; color: var(--text) !important;
    font-size: 0.95rem !important; padding: 10px 16px !important; resize: none !important;
}
[data-testid="stTextArea"] textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important; }

[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"] { background: transparent !important; border: none !important; padding: 4px 0 !important; }
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploadDropzone"] small { display: none !important; }
[data-testid="stFileUploaderDropzone"] > div > span,
[data-testid="stFileUploadDropzone"] > div > span { display: none !important; }
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: 14px !important; color: var(--text) !important; width: 100% !important;
    padding: 14px 20px !important; font-size: 0.92rem !important; font-weight: 500 !important; justify-content: center !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover { border-color: var(--accent) !important; }

[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; color: var(--text) !important; }
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul { background: var(--surface) !important; }
[data-baseweb="menu"] li { color: var(--text) !important; }
[data-baseweb="menu"] li:hover { background: var(--sidebar) !important; }

[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: var(--text) !important; }

.feature-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 20px 0 12px; }
.feature-card { background: var(--surface); border-radius: var(--radius); padding: 14px 12px; text-align: center; border: 1px solid var(--border); }
.feature-card:hover { border-color: var(--accent); }
.feature-icon { font-size: 1.5rem; margin-bottom: 6px; }
.feature-title { font-size: 0.88rem; font-weight: 600; color: var(--text) !important; margin-bottom: 4px; }
.feature-desc { font-size: 0.75rem; color: var(--text-muted) !important; line-height: 1.4; }

button[kind="secondary"][data-testid*="wb_add"] {
    font-size: 0.75rem !important; color: var(--text-muted) !important;
    border-color: var(--border) !important; padding: 2px 10px !important;
    height: auto !important; min-height: 28px !important; border-radius: 14px !important; background: transparent !important;
}

.login-logo { text-align: center; padding: 60px 0 24px; }
.login-logo-icon { font-size: 3rem; }
.login-logo-title { font-size: 1.5rem; font-weight: 600; color: var(--text) !important; margin: 8px 0 4px; }
.login-logo-sub { font-size: 0.85rem; color: var(--text-muted) !important; }

@media (max-width: 768px) {
    [data-testid="stSidebar"] {
        display: block !important; position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 82vw !important; max-width: 300px !important; height: 100vh !important;
        z-index: 9998 !important; overflow-y: auto !important;
        transform: translateX(-110%) !important;
        transition: transform 0.26s cubic-bezier(.4,0,.2,1) !important;
    }
    [data-testid="stSidebar"].ma-sb-open { transform: translateX(0) !important; box-shadow: 6px 0 32px rgba(0,0,0,0.2) !important; }
    #ma-hamburger {
        display: flex !important; position: fixed !important;
        top: 10px !important; left: 10px !important; z-index: 9999 !important;
        width: 40px !important; height: 40px !important;
        background: rgba(255,255,255,0.95) !important; border: 1px solid var(--border) !important;
        border-radius: 11px !important; align-items: center !important; justify-content: center !important;
        cursor: pointer !important; box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        font-size: 1.2rem !important; user-select: none !important; -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop {
        display: none; position: fixed !important; inset: 0 !important;
        background: rgba(0,0,0,0.35) !important; z-index: 9997 !important; -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop.active { display: block !important; }
    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 4px !important; }
    [data-testid="stColumn"] { min-width: 0 !important; flex-shrink: 1 !important; overflow: hidden !important; }
    .bubble-user { max-width: 80vw !important; font-size: 0.9rem !important; }
    .bubble-asst-wrap { font-size: 0.9rem !important; }
    .greeting-main { font-size: 1.4rem !important; }
    .toolbar-model [data-testid="stSelectbox"] > div > div { font-size: 0.68rem !important; padding: 2px 6px !important; min-height: 32px !important; }
    .toolbar-btn button { width: 36px !important; height: 36px !important; font-size: 1.1rem !important; }
    .av { width: 28px !important; height: 28px !important; font-size: 0.9rem !important; }
    .app-header-title { font-size: 0.9rem !important; }
    [data-testid="stChatInputTextArea"] { font-size: 0.9rem !important; }
    .feature-card { padding: 10px 8px; }
    .feature-title { font-size: 0.82rem !important; }
    .feature-desc { font-size: 0.7rem !important; }
}
</style>
"""

_DARK_CSS = """
<style>
:root {
    --dm-bg:       #0D0D14;
    --dm-surface:  #16162A;
    --dm-sidebar:  #121224;
    --dm-border:   #282845;
    --dm-text:     #DEE1F5;
    --dm-muted:    #6B6B95;
    --dm-accent:   #5B8CFF;
    --dm-user-bg:  #1A2F60;
    --dm-user-text:#C0D5FF;
    --dm-card:     #1E1E38;
    --dm-card2:    #242448;
}

html, body { background: var(--dm-bg) !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container, footer,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"] { background: var(--dm-bg) !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4, h5, h6 { color: var(--dm-text) !important; }

header[data-testid="stHeader"] { background: var(--dm-surface) !important; border-bottom: 1px solid var(--dm-border) !important; }

[data-testid="stSidebar"] { background: var(--dm-sidebar) !important; border-right: 1px solid var(--dm-border) !important; }
[data-testid="stSidebar"] * { color: var(--dm-text) !important; }
[data-testid="stSidebar"] .stButton button { background: var(--dm-card) !important; border: 1px solid var(--dm-border) !important; color: var(--dm-text) !important; }
[data-testid="stSidebar"] .stButton button:hover { background: var(--dm-card2) !important; color: #fff !important; border-color: var(--dm-accent) !important; }

.course-banner { background: var(--dm-card) !important; color: var(--dm-muted) !important; border-color: var(--dm-border) !important; }
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }
[data-testid="element-container"] { background: transparent !important; }

.bubble-user { background: var(--dm-user-bg) !important; color: var(--dm-user-text) !important; border-radius: 18px 4px 18px 18px !important; }

.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div { background: var(--dm-card) !important; border: 1px solid var(--dm-border) !important; color: var(--dm-text) !important; }
.bubble-asst-wrap { background: var(--dm-card) !important; border: 1px solid var(--dm-border) !important; }
.bubble-asst-wrap p, .bubble-asst-wrap li { color: var(--dm-text) !important; }

pre, pre code, code { background: #0A0A1A !important; color: #B8C8E8 !important; border: 1px solid var(--dm-border) !important; }
[data-testid="stCodeBlock"], [data-testid="stCode"],
[data-testid="stCodeBlock"] > div, [data-testid="stCode"] > div,
.stCodeBlock, .stCodeBlock > div { background: #0A0A1A !important; }
[data-testid="stCodeBlock"] pre, [data-testid="stCode"] pre { background: #0A0A1A !important; }
[data-testid="stCodeBlock"] button, [data-testid="stCode"] button { background: var(--dm-card) !important; color: var(--dm-muted) !important; border: 1px solid var(--dm-border) !important; }

.stMarkdown img, [data-testid="stMarkdownContainer"] img { filter: brightness(0.88) contrast(1.05) !important; border-radius: 6px !important; }

[data-testid="stVerticalBlock"] [data-testid="stButton"] button { background: var(--dm-surface) !important; border: 1px solid var(--dm-border) !important; color: var(--dm-text) !important; box-shadow: none !important; }
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover { background: var(--dm-card2) !important; border-color: var(--dm-accent) !important; color: #fff !important; }

.feature-card { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; }
.feature-card:hover { border-color: var(--dm-accent) !important; }
.feature-title { color: var(--dm-text) !important; }
.feature-desc { color: var(--dm-muted) !important; }
.greeting-main, .welcome-title { color: var(--dm-text) !important; }
.greeting-sub, .welcome-sub { color: var(--dm-muted) !important; }

[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: var(--dm-bg) !important; }
[data-testid="stChatInputContainer"] { background: var(--dm-surface) !important; border: 1.5px solid var(--dm-border) !important; border-radius: 24px !important; padding: 8px 14px !important; margin: 0 0 10px !important; box-shadow: none !important; }
[data-testid="stChatInputContainer"]:focus-within { border-color: var(--dm-accent) !important; box-shadow: 0 0 0 3px rgba(91,140,255,0.15) !important; }
[data-testid="stChatInputTextArea"] { background: transparent !important; border: none !important; box-shadow: none !important; border-radius: 0 !important; color: var(--dm-text) !important; padding: 2px 0 !important; }
[data-testid="stChatInputTextArea"]:focus { box-shadow: none !important; border: none !important; }
[data-testid="stChatInputSubmitButton"] button { background: var(--dm-accent) !important; }

[data-testid="stHorizontalBlock"]:has(.toolbar-btn) { background: var(--dm-bg) !important; }
.toolbar-model [data-testid="stSelectbox"] > div > div { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; color: var(--dm-text) !important; }
.toolbar-btn button { color: var(--dm-muted) !important; }
.toolbar-btn button:hover { background: var(--dm-card) !important; color: var(--dm-text) !important; }

[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button { background: var(--dm-surface) !important; border: 1px solid var(--dm-border) !important; color: var(--dm-text) !important; }
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover { background: var(--dm-card2) !important; border-color: var(--dm-accent) !important; }
[data-testid="stFileUploaderFileName"] { color: var(--dm-text) !important; }

[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div { background: var(--dm-surface) !important; border: 1px solid var(--dm-border) !important; color: var(--dm-text) !important; }
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul, [data-baseweb="list"] { background: var(--dm-surface) !important; }
[data-baseweb="menu"] li, [data-baseweb="option"] { color: var(--dm-text) !important; }
[data-baseweb="menu"] li:hover, [data-baseweb="option"]:hover { background: var(--dm-card2) !important; }

.plus-panel { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; }
.plus-panel .stButton button { background: var(--dm-card) !important; border-color: var(--dm-border) !important; color: var(--dm-text) !important; }
.plus-panel .stButton button:hover { background: var(--dm-card2) !important; border-color: var(--dm-accent) !important; }

[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; }
[data-testid="stAudioInput"] button { color: var(--dm-muted) !important; }

[data-testid="stTextArea"] textarea { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; color: var(--dm-text) !important; }

.guide-chip { background: var(--dm-card) !important; border-color: var(--dm-border) !important; color: var(--dm-muted) !important; }
.guide-chip.on { background: var(--dm-accent) !important; border-color: var(--dm-accent) !important; color: #fff !important; }

[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: var(--dm-text) !important; }
[data-testid="stToggle"] { color: var(--dm-text) !important; }
[data-testid="stAlert"] { background: var(--dm-card) !important; border-color: var(--dm-border) !important; }
[data-testid="stAlert"] p { color: var(--dm-text) !important; }
[data-testid="stExpander"] { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; }
[data-testid="stExpander"] summary { color: var(--dm-text) !important; }
details, details summary { background: var(--dm-surface) !important; color: var(--dm-text) !important; }

hr { border-color: var(--dm-border) !important; }
small, .caption { color: var(--dm-muted) !important; }

.login-logo-title { color: var(--dm-text) !important; }
.login-logo-sub { color: var(--dm-muted) !important; }

div[data-testid="stPills"] button { background: var(--dm-card) !important; border-color: var(--dm-border) !important; color: var(--dm-text) !important; }
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-selected="true"] { background: var(--dm-accent) !important; color: #fff !important; }

[data-testid="stStatusWidget"] { background: var(--dm-surface) !important; border-color: var(--dm-border) !important; }

.katex-display { background: transparent !important; color: var(--dm-text) !important; }
.katex, .katex * { color: var(--dm-text) !important; background: transparent !important; }
.katex .fbox, .katex .fbox > .katex-html { border-color: #7a7ab8 !important; background: transparent !important; }
.katex .frac-line { background: var(--dm-text) !important; border-color: var(--dm-text) !important; }
.katex svg path, .katex .svg-align path { fill: var(--dm-text) !important; stroke: var(--dm-text) !important; }
.katex .delimsizing path, .katex .stretchy path { fill: var(--dm-text) !important; }

mjx-container { background: transparent !important; color: var(--dm-text) !important; }
mjx-container * { color: var(--dm-text) !important; background: transparent !important; }
mjx-container svg, mjx-container svg * { fill: var(--dm-text) !important; }
mjx-container[jax="CHTML"] { color: var(--dm-text) !important; }
mjx-menclose { border-color: #7a7ab8 !important; }
mjx-mfrac > mjx-frac > mjx-line { border-color: var(--dm-text) !important; }

.MathJax_Display, .MathJax, .MJXc-display { background: transparent !important; color: var(--dm-text) !important; }
.MathJax svg { fill: var(--dm-text) !important; }

.stMarkdownContainer .math, .stMarkdown .math { background: transparent !important; }
[data-testid="stMarkdownContainer"] > div { background: transparent !important; }
</style>
"""
