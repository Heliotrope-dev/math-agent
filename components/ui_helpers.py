"""CSS and JS strings for Math Agent UI."""

_BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
@import url('https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
/* AI 回复区域使用霞鹜文楷手写体 */
.bubble-asst-inner { font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif; font-size: 1rem; line-height: 1.8; }

/* ══ 全局背景：微信暖米白 ══ */
html, body { background: #EDE5DC !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"],
footer { background: #EDE5DC !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4 { color: #1a1a1a !important; }
#MainMenu, header { visibility: hidden; }
[data-testid="block-container"] { padding-bottom: 180px !important; }

/* ── 侧边栏 ── */
[data-testid="stSidebar"] {
    background: #F0EBE5 !important;
    border-right: 1px solid #D5CEC8 !important;
}
[data-testid="stSidebar"] * { color: #2a2a2a !important; }
[data-testid="stSidebar"] .stButton button {
    background: #E8E2DC !important;
    border: 1px solid #CCC6C0 !important;
    color: #444 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #DEDAD4 !important; color: #111 !important;
}

/* ── Streamlit 顶栏：与页面背景融合，保留侧栏开关 ── */
header[data-testid="stHeader"] {
    background: #F5F0EB !important;
    box-shadow: none !important;
    border-bottom: none !important;
}
/* 只隐藏顶部彩色装饰条，不隐藏工具栏 */
header[data-testid="stHeader"] [data-testid="stDecoration"] {
    display: none !important;
}
.main .block-container { padding-top: 0.5rem !important; }

/* ── 课程横幅 ── */
.course-banner {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; margin-bottom: 12px;
    background: #EEE8E1; border-radius: 8px;
    font-size: 0.9rem; font-weight: 600; color: #555;
}

/* ── 顶部标题 ── */
.app-header {
    display: flex; align-items: center; gap: 10px;
    padding: 0.5rem 0 1rem; border-bottom: 1px solid #D4CEC8;
}
.app-header-title { font-size: 1rem; font-weight: 600; color: #555 !important; }

/* ── 欢迎页 ── */
.welcome-wrap { text-align: center; padding: 2.5rem 0 1.5rem; }
.welcome-title { font-size: 1.8rem; font-weight: 600; color: #1a1a1a !important; margin-bottom: 0.5rem; }
.welcome-sub { font-size: 0.88rem; color: #888 !important; margin-bottom: 2rem; }

/* ── 示例卡片 ── */
[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: #FFFFFF !important;
    border: 1px solid #D5CEC8 !important;
    border-radius: 12px !important;
    color: #333 !important;
    font-size: 0.85rem !important;
    padding: 12px 16px !important;
    text-align: left !important;
    line-height: 1.45 !important;
    min-height: 56px !important;
    height: auto !important;
    white-space: normal !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    background: #F5F0EB !important;
    border-color: #A8A0A0 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 8px rgba(0,0,0,0.1) !important;
}

/* ── 换一批 ── */
.refresh-btn button {
    background: transparent !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 20px !important;
    color: #888 !important; font-size: 0.82rem !important;
}
.refresh-btn button:hover { border-color: #999 !important; color: #444 !important; }

/* ── 用户气泡（右对齐，无头像）── */
.msg-row-user {
    display: flex;
    justify-content: flex-end;
    margin: 6px 0 6px;
}
.bubble-user {
    background: #95EC69;
    color: #111;
    border-radius: 18px 4px 18px 18px;
    padding: 10px 14px;
    word-break: break-word;
    line-height: 1.6;
    font-size: 0.95rem;
    display: inline-block;
    max-width: 72%;
}
/* ── AI 回答（左对齐，无头像，全宽）── */
.bubble-asst-wrap {
    background: #FFFFFF;
    border-radius: 4px 18px 18px 18px;
    padding: 10px 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    word-break: break-word;
    line-height: 1.6;
    font-size: 0.95rem;
}
.bubble-asst-wrap p, .bubble-asst-wrap li { color: #1a1a1a !important; }
.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div {
    background: #FFFFFF;
    border-radius: 4px 18px 18px 18px;
    padding: 10px 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif;
    font-size: 1rem;
    line-height: 1.8;
    word-break: break-word;
}

/* ── 引导模式开关条 ── */
.guide-bar { display: flex; align-items: center; gap: 8px; padding: 2px 0 4px; }
.guide-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: #E8E2DC; border: 1px solid #C8C2BC; border-radius: 20px;
    padding: 4px 12px; font-size: 0.82rem; color: #555;
    cursor: pointer; user-select: none; transition: all 0.15s;
}
.guide-chip.on { background: #2aae67; border-color: #2aae67; color: #fff; }

/* ── 加号面板 ── */
.plus-panel {
    background: #F5F0EB; border: 1px solid #D4CEC8;
    border-radius: 16px; padding: 16px 12px; margin: 8px 0;
}
.plus-panel .stButton button {
    background: #FFFFFF !important; border: 1px solid #D0CAC4 !important;
    border-radius: 12px !important; padding: 14px 6px !important;
    height: 76px !important; font-size: 0.82rem !important; color: #444 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
.plus-panel .stButton button:hover {
    background: #EDE5DC !important; border-color: #AAA !important; color: #111 !important;
}

/* ── 工具栏图标按钮 ── */
.toolbar-btn button {
    background: transparent !important; border: none !important;
    font-size: 1.4rem !important; padding: 6px !important;
    border-radius: 50% !important; color: #666 !important;
    height: 44px !important; width: 44px !important;
}
.toolbar-btn button:hover { background: #D8D0C8 !important; color: #222 !important; }

/* ── 输入框：外框即输入区，内部 textarea 透明（去掉套娃黑块）── */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: #EDE5DC !important; }
[data-testid="stChatInputContainer"] {
    background: #FFFFFF !important;
    border: 1.5px solid #C8C0B8 !important;
    border-radius: 24px !important;
    padding: 8px 14px 8px !important;
    margin: 0 0 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
}
[data-testid="stChatInputContainer"]:focus-within {
    border-color: #2aae67 !important;
    box-shadow: 0 0 0 2px rgba(42,174,103,0.15) !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}
[data-testid="stChatInputSubmitButton"] button {
    background: #2aae67 !important; border-radius: 50% !important;
}
/* ── 工具栏与横幅：随内容区等宽，sticky 吸附在输入框上方 ── */
[data-testid="stHorizontalBlock"]:has(.toolbar-btn) {
    position: sticky !important;
    bottom: 72px !important;
    z-index: 200 !important;
    background: #EDE5DC !important;
    padding: 4px 0 2px !important;
    margin: 0 !important;
}
.course-banner-row [data-testid="stHorizontalBlock"],
[data-testid="stHorizontalBlock"]:has(.course-banner) {
    align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has(.course-banner) [data-testid="stButton"] button {
    height: 100% !important; min-height: 42px !important;
}

/* ── 知识点 pills（全覆盖，优先级最高）── */
[data-testid="stPills"] { margin-top: 8px !important; }
div[data-testid="stPills"] > div > label > div,
div[data-testid="stPills"] button,
div[data-testid="stPills"] [role="radio"],
div[data-testid="stPills"] [role="button"] {
    background-color: #F0EBE5 !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 20px !important;
    color: #444444 !important;
    font-size: 0.78rem !important;
    padding: 3px 12px !important;
}
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-selected="true"],
div[data-testid="stPills"] [aria-checked="true"],
div[data-testid="stPills"] [aria-selected="true"] {
    background-color: #2aae67 !important;
    border-color: #2aae67 !important;
    color: #ffffff !important;
}
div[data-testid="stPills"] p,
div[data-testid="stPills"] span { color: inherit !important; background: transparent !important; }

/* ── 通用按钮 ── */
.stButton button { border-radius: 8px !important; font-size: 0.84rem !important; }
.stButton button[kind="primary"] {
    background: #2aae67 !important; border: none !important; color: #fff !important;
}
.stButton button[kind="primary"]:hover { background: #25a05e !important; }

/* ── 轮次标签 ── */
.turn-badge {
    display: inline-block; background: #E8E2DC; border: 1px solid #C8C0B8;
    color: #888; padding: 1px 8px; border-radius: 6px; font-size: 0.7rem; margin-bottom: 4px;
}

/* ── expander ── */
[data-testid="stExpander"] {
    border: 1px solid #D4CEC8 !important; border-radius: 10px !important;
    background: #F5F0EB !important;
}

/* ── Status ── */
[data-testid="stStatusWidget"] {
    background: #F5F0EB !important; border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
}

/* ── 代码块 ── */
pre, code {
    background: #F0EBE5 !important; border: 1px solid #D4CEC8 !important;
    border-radius: 8px !important; font-size: 0.82rem !important; color: #333 !important;
}

hr { border-color: #D4CEC8 !important; }

/* ── KaTeX 公式样式（课本感）── */
.katex-display {
    margin: 0.8em 0 !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
}
.katex { font-size: 1.05em !important; }
.katex-display > .katex { font-size: 1.1em !important; }

/* ── 麦克风 ── */
[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div {
    background: #F5F0EB !important; border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
}
/* 录音 / 停止 按钮放大 */
[data-testid="stAudioInput"] button {
    background: transparent !important; color: #555 !important;
    width: 72px !important; height: 72px !important;
    min-width: 72px !important; border-radius: 50% !important;
}
[data-testid="stAudioInput"] button svg {
    width: 36px !important; height: 36px !important;
}

/* ── 语音识别文本框（样式与聊天输入框一致）── */
[data-testid="stTextArea"] textarea {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 16px !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    padding: 10px 16px !important;
    resize: none !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #2aae67 !important;
    box-shadow: 0 0 0 2px rgba(42,174,103,0.15) !important;
}

/* ══ 文件上传：白色圆角按钮，隐藏虚线框和小字说明 ══ */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"] {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
}
/* 隐藏 "Drag and drop" / "200MB per file" 小字 */
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploadDropzone"] small {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] > div > span,
[data-testid="stFileUploadDropzone"] > div > span {
    display: none !important;
}
/* 上传按钮：全宽白色圆角 */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 14px !important;
    color: #333 !important;
    width: 100% !important;
    padding: 14px 20px !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    justify-content: center !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover {
    background: #F5F0EB !important;
    border-color: #888 !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
}
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul { background: #FFFFFF !important; }
[data-baseweb="menu"] li { color: #1a1a1a !important; }
[data-baseweb="menu"] li:hover { background: #F0EBE5 !important; }

/* ── Checkbox / Toggle ── */
[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: #1a1a1a !important; }

/* ── 底部完全覆盖（包括 stBottom sticky 区域）── */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div {
    background: #EDE5DC !important;
}

/* ── 工具栏容器透明 ── */
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }
[data-testid="element-container"] { background: transparent !important; }

/* ── 工具栏里的 selectbox 紧凑 ── */
.toolbar-model [data-testid="stSelectbox"] > div > div {
    border: 1px solid #C8C0B8 !important;
    background: rgba(255,255,255,0.7) !important;
    font-size: 0.82rem !important;
    color: #333 !important;
    padding: 4px 10px !important;
    min-height: 36px !important;
    border-radius: 20px !important;
}

/* ── 欢迎问候语 ── */
.greeting-wrap {
    text-align: center;
    padding: 4rem 0 2rem;
}
.greeting-main {
    font-size: 2rem;
    font-weight: 600;
    color: #1a1a1a !important;
    margin-bottom: 0.4rem;
}
.greeting-sub {
    font-size: 0.9rem;
    color: #999 !important;
}

/* ── 侧边栏历史记录 ── */
[data-testid="stSidebar"] .stButton button {
    text-align: left !important;
    font-size: 0.8rem !important;
    padding: 6px 10px !important;
    height: auto !important;
    min-height: 32px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: block !important;
}

/* ── 功能介绍卡片 ── */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin: 20px 0 12px;
}
.feature-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 14px 12px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    border: 1px solid #EAE4DE;
}
.feature-icon { font-size: 1.5rem; margin-bottom: 6px; }
.feature-title { font-size: 0.88rem; font-weight: 600; color: #1a1a1a !important; margin-bottom: 4px; }
.feature-desc { font-size: 0.75rem; color: #888 !important; line-height: 1.4; }


/* ── 存入错题本 ── */
button[kind="secondary"][data-testid*="wb_add"] {
    font-size: 0.75rem !important;
    color: #888 !important;
    border-color: #DDD !important;
    padding: 2px 10px !important;
    height: auto !important;
    min-height: 28px !important;
    border-radius: 14px !important;
    background: transparent !important;
}

/* ── 登录页 ── */
.login-logo {
    text-align: center;
    padding: 60px 0 24px;
}
.login-logo-icon { font-size: 3rem; }
.login-logo-title { font-size: 1.5rem; font-weight: 600; color: #1a1a1a !important; margin: 8px 0 4px; }
.login-logo-sub { font-size: 0.85rem; color: #888 !important; }

/* ══ 手机端响应式 ══ */
@media (max-width: 768px) {
    /* 侧边栏：改为左滑覆盖层，默认隐藏在屏幕左侧 */
    [data-testid="stSidebar"] {
        display: block !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 82vw !important; max-width: 300px !important;
        height: 100vh !important;
        z-index: 9998 !important;
        overflow-y: auto !important;
        transform: translateX(-110%) !important;
        transition: transform 0.26s cubic-bezier(.4,0,.2,1) !important;
    }
    [data-testid="stSidebar"].ma-sb-open {
        transform: translateX(0) !important;
        box-shadow: 6px 0 32px rgba(0,0,0,0.32) !important;
    }
    /* 汉堡按钮 */
    #ma-hamburger {
        display: flex !important;
        position: fixed !important;
        top: 10px !important; left: 10px !important;
        z-index: 9999 !important;
        width: 40px !important; height: 40px !important;
        background: rgba(255,255,255,0.93) !important;
        border: 1px solid #D4CEC8 !important;
        border-radius: 11px !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
        font-size: 1.2rem !important;
        user-select: none !important;
        -webkit-tap-highlight-color: transparent !important;
    }
    /* 半透明遮罩 */
    #ma-backdrop {
        display: none;
        position: fixed !important;
        inset: 0 !important;
        background: rgba(0,0,0,0.42) !important;
        z-index: 9997 !important;
        -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop.active { display: block !important; }
    /* 强制所有列横排，不折行 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }
    [data-testid="stColumn"] {
        min-width: 0 !important;
        flex-shrink: 1 !important;
        overflow: hidden !important;
    }
    /* 气泡宽度自适应 */
    .bubble-user { max-width: 80vw !important; font-size: 0.9rem !important; }
    .bubble-asst-wrap { font-size: 0.9rem !important; }
    /* 欢迎语 */
    .greeting-main { font-size: 1.4rem !important; }
    /* 工具栏在小屏更紧凑 */
    .toolbar-model [data-testid="stSelectbox"] > div > div {
        font-size: 0.68rem !important; padding: 2px 6px !important; min-height: 32px !important;
    }
    .toolbar-btn button {
        width: 36px !important; height: 36px !important; font-size: 1.1rem !important;
    }
    /* 头像缩小 */
    .av { width: 28px !important; height: 28px !important; font-size: 0.9rem !important; }
    /* 头部 */
    .app-header-title { font-size: 0.9rem !important; }
    /* 输入框 */
    [data-testid="stChatInputTextArea"] { font-size: 0.9rem !important; }
    /* 功能卡片 */
    .feature-card { padding: 10px 8px; }
    .feature-title { font-size: 0.82rem !important; }
    .feature-desc { font-size: 0.7rem !important; }
}
</style>
"""

_DARK_CSS = """
<style>
/* ═══ 夜间模式 — 深海蓝调 ═══ */
:root {
    --dm-bg:        #0f0f17;
    --dm-panel:     #18182a;
    --dm-card:      #20203a;
    --dm-card2:     #252540;
    --dm-border:    #32325a;
    --dm-text:      #dde0f5;
    --dm-muted:     #7070a0;
    --dm-accent:    #5a8cff;
    --dm-user-bg:   #1a3a5e;
    --dm-user-text: #a8d0f0;
    --dm-user-av:   #1e4880;
}

/* ══ 全局背景 & 文字 ══ */
html, body { background: var(--dm-bg) !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container, footer,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"] { background: var(--dm-bg) !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4, h5, h6 { color: var(--dm-text) !important; }

/* ══ 侧边栏 ══ */
[data-testid="stSidebar"] {
    background: var(--dm-panel) !important;
    border-right: 1px solid var(--dm-border) !important;
}
[data-testid="stSidebar"] * { color: var(--dm-text) !important; }
[data-testid="stSidebar"] .stButton button {
    background: var(--dm-card) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: var(--dm-card2) !important; color: #fff !important;
    border-color: var(--dm-accent) !important;
}

/* ══ 顶栏 ══ */
header[data-testid="stHeader"] { background: var(--dm-panel) !important; }

/* ══ 课程横幅 & 退出按钮容器 ══ */
.course-banner { background: var(--dm-card) !important; color: var(--dm-muted) !important; }
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }

/* ══ 用户气泡 — 深蓝调代替微信绿 ══ */
.bubble-user {
    background: var(--dm-user-bg) !important;
    color: var(--dm-user-text) !important;
    border-radius: 18px 4px 18px 18px !important;
}

/* ══ AI 气泡 ══ */
.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div {
    background: var(--dm-card) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.6) !important;
    color: var(--dm-text) !important;
}
.bubble-asst-wrap {
    background: var(--dm-card) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.6) !important;
}
.bubble-asst-wrap p, .bubble-asst-wrap li { color: var(--dm-text) !important; }

/* ══ 代码块（文字思维导图等）══ */
pre, pre code, code {
    background: #12122a !important;
    color: #b8c8e8 !important;
    border: 1px solid var(--dm-border) !important;
}
[data-testid="stCodeBlock"], [data-testid="stCode"],
[data-testid="stCodeBlock"] > div, [data-testid="stCode"] > div,
.stCodeBlock, .stCodeBlock > div { background: #12122a !important; }
[data-testid="stCodeBlock"] pre, [data-testid="stCode"] pre { background: #12122a !important; }
/* 代码块复制按钮 */
[data-testid="stCodeBlock"] button, [data-testid="stCode"] button {
    background: var(--dm-card) !important; color: var(--dm-muted) !important;
    border: 1px solid var(--dm-border) !important;
}

/* ══ 思维导图/函数图像（matplotlib PNG）── 轻度暗化 ══ */
.stMarkdown img, [data-testid="stMarkdownContainer"] img {
    filter: brightness(0.88) contrast(1.05) !important;
    border-color: var(--dm-border) !important;
    border-radius: 6px !important;
}

/* ══ 示例卡片 ══ */
[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3) !important;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    background: var(--dm-card2) !important;
    border-color: var(--dm-accent) !important; color: #fff !important;
}

/* ══ 功能卡片 ══ */
.feature-card { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
.feature-title { color: var(--dm-text) !important; }
.feature-desc { color: var(--dm-muted) !important; }

/* ══ 欢迎语 ══ */
.greeting-main, .welcome-title { color: var(--dm-text) !important; }
.greeting-sub, .welcome-sub { color: var(--dm-muted) !important; }

/* ══ 输入框 & 底栏（去掉套娃黑块：外框为可见盒子，内部 textarea 透明）══ */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: var(--dm-bg) !important; }
[data-testid="stChatInputContainer"] {
    background: var(--dm-panel) !important;
    border: 1.5px solid var(--dm-border) !important;
    border-radius: 24px !important;
    padding: 8px 14px 8px !important;
    margin: 0 0 10px !important;
    box-shadow: none !important;
}
[data-testid="stChatInputContainer"]:focus-within {
    border-color: var(--dm-accent) !important;
    box-shadow: 0 0 0 2px rgba(90,140,255,0.2) !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    color: var(--dm-text) !important;
    padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus {
    box-shadow: none !important; border: none !important;
}
[data-testid="stChatInputSubmitButton"] button { background: #2a6edd !important; }
/* 工具栏 sticky */
[data-testid="stHorizontalBlock"]:has(.toolbar-btn) {
    background: var(--dm-bg) !important;
}

/* ══ 文件上传 ══ */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover {
    background: var(--dm-card2) !important; border-color: var(--dm-accent) !important;
}
[data-testid="stFileUploaderFileName"] { color: var(--dm-text) !important; }

/* ══ Selectbox / 下拉菜单 ══ */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul, [data-baseweb="list"] { background: var(--dm-panel) !important; }
[data-baseweb="menu"] li, [data-baseweb="option"] { color: var(--dm-text) !important; }
[data-baseweb="menu"] li:hover, [data-baseweb="option"]:hover { background: var(--dm-card2) !important; }

/* ══ Plus 面板 ══ */
.plus-panel { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
.plus-panel .stButton button {
    background: var(--dm-card) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
.plus-panel .stButton button:hover {
    background: var(--dm-card2) !important; border-color: var(--dm-accent) !important;
}

/* ══ 工具栏 ══ */
.toolbar-model [data-testid="stSelectbox"] > div > div {
    background: rgba(24,24,42,0.98) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
.toolbar-btn button { color: var(--dm-muted) !important; }
.toolbar-btn button:hover { background: var(--dm-card) !important; color: var(--dm-text) !important; }

/* ══ 麦克风 ══ */
[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div {
    background: var(--dm-panel) !important; border-color: var(--dm-border) !important;
}
[data-testid="stAudioInput"] button { color: var(--dm-muted) !important; }

/* ══ 语音/文字输入 ══ */
[data-testid="stTextArea"] textarea {
    background: var(--dm-panel) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}

/* ══ Guide Chip ══ */
.guide-chip { background: var(--dm-card) !important; border-color: var(--dm-border) !important; color: var(--dm-muted) !important; }
.guide-chip.on { background: #2a6edd !important; border-color: #2a6edd !important; color: #fff !important; }

/* ══ Checkbox / Toggle ══ */
[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: var(--dm-text) !important; }
[data-testid="stToggle"] { color: var(--dm-text) !important; }

/* ══ Info / Warning / Error 提示块 ══ */
[data-testid="stAlert"] { background: var(--dm-card) !important; border-color: var(--dm-border) !important; }
[data-testid="stAlert"] p { color: var(--dm-text) !important; }

/* ══ Expander ══ */
[data-testid="stExpander"] { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
[data-testid="stExpander"] summary { color: var(--dm-text) !important; }
details, details summary { background: var(--dm-panel) !important; color: var(--dm-text) !important; }

/* ══ 分割线 & 小字 ══ */
hr { border-color: var(--dm-border) !important; }
small, .caption { color: var(--dm-muted) !important; }

/* ══ 登录页 ══ */
.login-logo-title { color: var(--dm-text) !important; }
.login-logo-sub { color: var(--dm-muted) !important; }

/* ══ Pills（知识点标签）══ */
div[data-testid="stPills"] button {
    background: var(--dm-card) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-selected="true"] {
    background: var(--dm-accent) !important; color: #fff !important;
}

/* ══ 元素容器通用 ══ */
[data-testid="element-container"] { background: transparent !important; }

/* ══ KaTeX 暗色适配 ══ */
.katex-display { background: transparent !important; color: #dde0f5 !important; }
.katex, .katex * { color: #dde0f5 !important; background: transparent !important; }
.katex .fbox, .katex .fbox > .katex-html { border-color: #7a7ab8 !important; background: transparent !important; }
.katex .frac-line { background: #dde0f5 !important; border-color: #dde0f5 !important; }
.katex svg path, .katex .svg-align path { fill: #dde0f5 !important; stroke: #dde0f5 !important; }
.katex .delimsizing path, .katex .stretchy path { fill: #dde0f5 !important; }

/* ══ MathJax 3（Streamlit 内置）暗色适配 ══ */
mjx-container { background: transparent !important; color: #dde0f5 !important; }
mjx-container * { color: #dde0f5 !important; background: transparent !important; }
mjx-container svg, mjx-container svg * { fill: #dde0f5 !important; }
mjx-container[jax="CHTML"] { color: #dde0f5 !important; }
/* \boxed{} 边框 */
mjx-menclose { border-color: #7a7ab8 !important; }
mjx-mfrac > mjx-frac > mjx-line { border-color: #dde0f5 !important; }

/* ══ MathJax 2 降级兼容 ══ */
.MathJax_Display, .MathJax, .MJXc-display { background: transparent !important; color: #dde0f5 !important; }
.MathJax svg { fill: #dde0f5 !important; }

/* ══ Streamlit 数学块容器 ══ */
.stMarkdownContainer .math, .stMarkdown .math { background: transparent !important; }
[data-testid="stMarkdownContainer"] > div { background: transparent !important; }
</style>
"""
