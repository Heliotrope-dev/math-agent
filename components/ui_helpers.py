"""CSS and JS strings for Math Agent UI.

2026-09前端重做：跟finance-agent那套"灰白克制"的视觉系统对齐——同一份Inter
字体、同一套墨色(ink)分级、同一套三档按钮（次要描边/主要实底/安静无边框）、
同一套"不画框，用发丝线分隔"的列表处理。主色调统一黑白灰，不用蓝紫这类品牌
色——math-agent原来的蓝色强调色(#2563EB)+紫色用户气泡(#7B5CFA)撤掉，聊天
气泡也改成墨色深浅对比而不是彩色。全站唯一保留的饱和色是删除/取消这类破坏性
操作的悬停提示（红色，跟finance-agent的删除图标同一个色号#D0342C），只在真正
需要强调的地方才出现，不做成装饰。深色模式一并撤掉（finance-agent那边已经
验证过"用户反馈按了跟没按一样，很烦"，不再维护两套主题）。
"""

_BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:wght@500;600&display=swap');

[data-testid="stSidebarNav"] { display: none !important; }

:root {
    /* 画布：只有三层——底、卡面、更浅的填充块。跟finance-agent同一套数值。 */
    --ma-bg:        #FBFBF9;
    --ma-surface:   #FFFFFF;
    --ma-fill:      #F5F5F2;
    --ma-border:    #E5E5E0;
    --ma-border-2:  #D7D7D1;

    /* 文字：四级 */
    --ma-text:      #2A2C30;
    --ma-text-2:    #55585D;
    --ma-muted:     #858887;
    --ma-faint:     #AAACAA;

    /* 界面强调色用墨色，不用彩色——跟finance-agent同一条原则，主色调黑白灰。
       全站唯一允许出现的饱和色是破坏性操作（删除/取消）悬停时的红色提示，
       跟finance-agent的删除图标同一个色号，只用在真正需要强调的地方。 */
    --ma-ink:       #62666C;
    --ma-danger:    #D0342C;

    --ma-radius:    8px;
    --ma-radius-sm: 6px;
}

/* ── 排版基线 ─────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'PingFang SC',
                 'Hiragino Sans GB', 'Microsoft YaHei', system-ui, sans-serif !important;
    color: var(--ma-text);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
.stApp, .stApp * { font-variant-numeric: tabular-nums; font-feature-settings: 'tnum' 1; }

html, body { background: var(--ma-bg) !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"],
section.main, .main, .block-container,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"],
footer {
    background: var(--ma-bg) !important;
    border: none !important; box-shadow: none !important; outline: none !important;
}
p, span, label, div, li, td, th, h1, h2, h3, h4 { color: var(--ma-text) !important; }
#MainMenu, header { visibility: hidden; }
[data-testid="stMainBlockContainer"] { padding-bottom: 180px !important; }

header[data-testid="stHeader"] {
    background: var(--ma-surface) !important;
    box-shadow: none !important;
    border-bottom: 1px solid var(--ma-border) !important;
}
header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
.main .block-container { padding-top: 0.5rem !important; }

.course-banner {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; margin-bottom: 12px;
    background: transparent; border: none; border-bottom: 1px solid var(--ma-border);
    font-size: 0.9rem; font-weight: 600; color: var(--ma-text-2);
}
.app-header {
    display: flex; align-items: center; gap: 10px;
    padding: 0.5rem 0 1rem; border-bottom: 1px solid var(--ma-border);
}
.app-header-title { font-size: 1rem; font-weight: 600; color: var(--ma-text-2) !important; }

.welcome-wrap { text-align: center; padding: 2.5rem 0 1.5rem; }
.welcome-title { font-family: 'Source Serif 4', 'Songti SC', STSong, serif !important; font-size: 1.85rem; font-weight: 600; letter-spacing: -0.012em; color: var(--ma-text) !important; margin-bottom: 0.5rem; }
.welcome-sub { font-size: 0.88rem; color: var(--ma-muted) !important; margin-bottom: 2rem; }
.greeting-wrap { text-align: center; padding: 4rem 0 2rem; }
.greeting-main { font-family: 'Source Serif 4', 'Songti SC', STSong, serif !important; font-size: 2rem; font-weight: 600; letter-spacing: -0.012em; color: var(--ma-text) !important; margin-bottom: 0.4rem; }
.greeting-sub { font-size: 0.9rem; color: var(--ma-muted) !important; }

/* 欢迎页大按钮（点开始学习之类）：跟finance-agent的次要按钮同一套描边，
   不再用悬停上浮+蓝色阴影这种效果——那是网页模板常见的"AI产品味儿"，
   finance-agent全站没有任何一处上浮/阴影动效，改成边框变深，跟发丝线
   的克制程度一致。 */
[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: transparent !important;
    border: 1px solid var(--ma-border) !important;
    border-radius: var(--ma-radius) !important;
    color: var(--ma-text) !important;
    font-size: 0.85rem !important; padding: 12px 16px !important;
    text-align: left !important; line-height: 1.45 !important;
    min-height: 56px !important; height: auto !important; white-space: normal !important;
    box-shadow: none !important;
    transition: border-color .15s ease, background .15s ease;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    border-color: var(--ma-border-2) !important;
    background: var(--ma-fill) !important;
}

/* ── 侧栏：功能保留（历史问题/错题本/学习档案是真实功能，不是finance-agent
   删掉的那种导航冗余），但外观改成同一套发丝线分隔的扁平列表，不画白盒子。
   这一段特意排在上面"通用按钮"规则之后——两条选择器特异度打平时源码
   靠后的赢，排前面会被上面那条通用按钮规则盖掉（实测踩过，侧栏按钮全变成
   了大号圆角描边盒子，不是发丝线扁平行）。 */
[data-testid="stSidebar"] {
    background: var(--ma-fill) !important;
    border-right: 1px solid var(--ma-border) !important;
    min-width: 264px !important;
    max-width: 264px !important;
}
[data-testid="stSidebar"] > div:first-child {
    width: 264px !important;
    padding: 20px 16px 18px !important;
}
[data-testid="stSidebar"] * { color: var(--ma-text) !important; }
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid var(--ma-border) !important;
    color: var(--ma-text-2) !important;
    border-radius: 0 !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    padding: 7px 4px !important;
    height: auto !important; min-height: 32px !important;
    white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
    display: flex !important;
    justify-content: flex-start !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton button p,
[data-testid="stSidebar"] .stButton button span {
    text-align: left !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(23,24,28,0.03) !important; color: var(--ma-text) !important;
}
/* 退出登录是独立的单个动作，不是列表项，不套用上面的扁平行样式——改成
   跟站内"安静"按钮一样的小号文字链接，不需要边框也不需要占满一行。 */
[data-testid="stSidebar"] [class*="st-key-logout_btn"] button {
    border: none !important; border-bottom: none !important;
    color: var(--ma-muted) !important; font-size: 0.78rem !important;
    padding: 4px 0 !important; width: auto !important; min-height: 0 !important;
}
[data-testid="stSidebar"] [class*="st-key-logout_btn"] button:hover {
    background: transparent !important; color: var(--ma-text) !important;
}

.refresh-btn button {
    background: transparent !important; border: 1px solid var(--ma-border) !important;
    border-radius: var(--ma-radius-sm) !important; color: var(--ma-muted) !important; font-size: 0.82rem !important;
}
.refresh-btn button:hover { border-color: var(--ma-border-2) !important; color: var(--ma-text) !important; }

/* page_link，跟 expander 一致的发丝线处理，不画卡片。 */
a[data-testid="stPageLink-NavLink"] {
    border: none !important;
    border-bottom: 1px solid var(--ma-border) !important;
    border-radius: 0 !important;
    background: transparent !important;
    padding: 10px 4px !important;
    font-size: 0.84rem !important;
    color: var(--ma-text) !important;
    text-decoration: none !important;
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    outline: none !important;
    box-shadow: none !important;
    transition: color 0.15s;
}
a[data-testid="stPageLink-NavLink"]:hover,
a[data-testid="stPageLink-NavLink"]:focus {
    color: var(--ma-text) !important;
    background: rgba(23,24,28,0.03) !important;
    outline: none !important;
    box-shadow: none !important;
}

/* 侧栏不是第二个内容页：用小型分组标题建立层级，避免连续的横线把所有
   功能挤成同一种列表项。 */
[data-testid="stSidebar"] .sb-section {
    margin: 22px 0 6px !important;
    color: var(--ma-muted) !important;
    font-size: 0.70rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.09em !important;
}
[data-testid="stSidebar"] .sb-section:first-of-type { margin-top: 16px !important; }

/* ── 消息：用户提问是三言两语，靠右墨色实底白字气泡，符合"这是一条消息"
   的直觉。AI的回答通常是好几段带公式的完整解题过程，不是三言两语——套用
   同款灰底气泡只会变成一整块灰色调，长内容里反而不美观，也不是finance-
   agent处理长内容的方式（它自己的报告类内容一律平铺，不装进气泡）。改成
   让AI回答平铺流动，靠字号/行距/段落间距把内容读出来，轮次之间用一条
   发丝线收尾，跟finance-agent的分区处理是同一套语言。不带头像图标，跟
   "不许有emoji/装饰图标"的硬规则一致。 */
.msg-row-user { display: flex; justify-content: flex-end; margin: 10px 0 6px; }
.bubble-user {
    background: var(--ma-ink) !important;
    color: #fff !important;
    border-radius: 12px !important;
    padding: 9px 13px; word-break: break-word; line-height: 1.6;
    font-size: 0.95rem; display: inline-block; max-width: 72%;
}

/* asst-bubble-marker 是紧挨在AI正文前面插入的一个空div，用来定位"下一个
   元素容器就是这条AI回答"——注意这里选的是 stElementContainer 这一层，
   不是 .stMarkdown：marker 和正文实际上是两个各自独立的 stElementContainer
   兄弟节点，.stMarkdown 本身互相并不相邻（各自套在自己的 stElementContainer
   里），选错这一层选择器完全不会命中，一开始就是这么踩的坑。 */
[data-testid="stElementContainer"]:has(.asst-bubble-marker) + [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] {
    font-family: 'Source Serif 4', 'Songti SC', STSong, serif !important;
    font-size: 1rem; line-height: 1.9; padding: 8px 0 22px;
    border-bottom: 1px solid var(--ma-border);
    margin-bottom: 14px;
}
[data-testid="stElementContainer"]:has(.asst-bubble-marker) + [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] p {
    margin: 0 0 12px;
}
[data-testid="stElementContainer"]:has(.asst-bubble-marker) + [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] p:last-child {
    margin-bottom: 0;
}

.guide-bar { display: flex; align-items: center; gap: 8px; padding: 2px 0 4px; }
.guide-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: transparent; border: 1px solid var(--ma-border); border-radius: 20px;
    padding: 4px 12px; font-size: 0.82rem; color: var(--ma-muted);
    cursor: pointer; user-select: none; transition: all 0.15s;
}
/* 选中态用墨色实底，跟主要按钮同一种"这是当前生效状态"的视觉语言，
   不再用蓝色——蓝色现在只留给聊天气泡。 */
.guide-chip.on { background: var(--ma-ink) !important; border-color: var(--ma-ink) !important; color: #fff !important; }

[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div {
    background: var(--ma-bg) !important;
    border: none !important; box-shadow: none !important;
}
[data-testid="stChatInput"] {
    background: var(--ma-surface) !important;
    border: 1.5px solid var(--ma-border-2) !important;
    border-radius: 18px !important;
    padding: 8px 14px !important; margin: 0 0 12px !important; box-shadow: none !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--ma-ink) !important;
    box-shadow: none !important;
}
[data-testid="stChatInput"] > div:first-child {
    background: transparent !important; border: none !important;
    box-shadow: none !important; border-radius: 0 !important;
}
[data-testid="stChatInput"] div:has(> [data-testid="stChatInputTextArea"]),
[data-testid="stChatInput"] div:has(> div > [data-testid="stChatInputTextArea"]) {
    background: transparent !important; border: none !important; box-shadow: none !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important; border: none !important;
    box-shadow: none !important; border-radius: 0 !important;
    color: var(--ma-text) !important; font-size: 0.95rem !important; padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus { box-shadow: none !important; border: none !important; outline: none !important; }
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInputSubmitButton"] button { background: var(--ma-ink) !important; border-radius: var(--ma-radius-sm) !important; }
[data-testid="stChatInputSubmitButton"] svg { fill: #fff !important; }
[data-testid="stChatInputSubmitButton"]:disabled,
[data-testid="stChatInputSubmitButton"] button:disabled {
    background: var(--ma-fill) !important; border: 1px solid var(--ma-border) !important; opacity: 1 !important;
}
[data-testid="stChatInputSubmitButton"]:disabled svg,
[data-testid="stChatInputSubmitButton"] button:disabled svg { fill: var(--ma-muted) !important; }
[data-testid="stChatInputFileUploadButton"] button,
[data-testid="stChatInputMicButton"],
[data-testid="stChatInputMicButton"] button {
    color: var(--ma-muted) !important; background: transparent !important;
}
[data-testid="stChatInputFileUploadButton"] svg,
[data-testid="stChatInputMicButton"] svg { fill: var(--ma-muted) !important; }
[data-testid="stChatInputFileUploadButton"] button:hover,
[data-testid="stChatInputMicButton"]:hover,
[data-testid="stChatInputMicButton"] button:hover { color: var(--ma-text) !important; }
[data-testid="stChatInputFileUploadButton"] button:hover svg,
[data-testid="stChatInputMicButton"]:hover svg,
[data-testid="stChatInputMicButton"] button:hover svg { fill: var(--ma-text) !important; }
[data-testid="stChatInputApproveButton"],
[data-testid="stChatInputApproveButton"] button { background: var(--ma-ink) !important; }
[data-testid="stChatInputApproveButton"] svg,
[data-testid="stChatInputApproveButton"] p { fill: #fff !important; color: #fff !important; }
[data-testid="stChatInputCancelButton"],
[data-testid="stChatInputCancelButton"] button { color: var(--ma-muted) !important; }
[data-testid="stChatInputCancelButton"] svg { fill: var(--ma-muted) !important; }

.course-banner-row [data-testid="stHorizontalBlock"],
[data-testid="stHorizontalBlock"]:has(.course-banner) { align-items: stretch !important; }
[data-testid="stHorizontalBlock"]:has(.course-banner) [data-testid="stButton"] button {
    height: 100% !important; min-height: 42px !important;
}
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }
[data-testid="stElementContainer"] { background: transparent !important; }

/* ── 分段控件（引导模式等pills）：跟finance-agent的stButtonGroup同一套——
   未选中描边、选中墨色实底，不再用圆胶囊+蓝色。 */
[data-testid="stButtonGroup"] { margin-top: 8px !important; }
div[data-testid="stButtonGroup"] > div > label > div,
div[data-testid="stButtonGroup"] button,
div[data-testid="stButtonGroup"] [role="radio"],
div[data-testid="stButtonGroup"] [role="button"] {
    background-color: var(--ma-surface) !important;
    border: 1px solid var(--ma-border) !important;
    border-radius: var(--ma-radius-sm) !important; color: var(--ma-muted) !important;
    font-size: 0.78rem !important; padding: 3px 12px !important;
}
div[data-testid="stButtonGroup"] button:hover,
div[data-testid="stButtonGroup"] button[aria-checked="true"],
div[data-testid="stButtonGroup"] button[aria-selected="true"],
div[data-testid="stButtonGroup"] [aria-checked="true"],
div[data-testid="stButtonGroup"] [aria-selected="true"] {
    background-color: var(--ma-ink) !important;
    border-color: var(--ma-ink) !important; color: #ffffff !important;
}
div[data-testid="stButtonGroup"] p,
div[data-testid="stButtonGroup"] span { color: inherit !important; background: transparent !important; }

/* ── 按钮：三档系统，跟finance-agent一字不差地照搬——次要(默认)=描边、
   主要=墨色实底、安静(tertiary)=悬停才浮出底色。 */
.stButton button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stPopover"] button {
    border-radius: var(--ma-radius-sm) !important; font-size: 0.84rem !important;
    box-shadow: none !important;
}
/* 按钮内的文字标签Streamlit会套一层<p>，页面顶部那条全局"p统一用--ma-text"
   规则(!important)直接挂在<p>上，子元素的直接样式天然盖过父级<button>上继承
   下来的color，不管父级选择器特异度多高——只在<button>上设color不够，必须
   连着内层<p>/div/span一起设，不然主要按钮会变成"黑底黑字"看不见文字
   （实测踩过，登录/注册按钮当时就是这样，看着像一块空白黑条）。 */
.stButton button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    background: var(--ma-ink) !important; border: 1px solid var(--ma-ink) !important; color: #fff !important;
}
.stButton button[kind="primary"] p,
.stButton button[kind="primary"] div,
.stButton button[kind="primary"] span,
[data-testid="stFormSubmitButton"] button[kind="primary"] p,
[data-testid="stFormSubmitButton"] button[kind="primary"] div,
[data-testid="stFormSubmitButton"] button[kind="primary"] span { color: #fff !important; }
.stButton button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover { background: #55595F !important; border-color: #55595F !important; }
.stButton button[kind="tertiary"], .stButton button[data-testid="stBaseButton-tertiary"] {
    background: transparent !important; border: 1px solid transparent !important; color: var(--ma-muted) !important;
}
.stButton button[kind="tertiary"] p,
.stButton button[kind="tertiary"] div,
.stButton button[kind="tertiary"] span,
.stButton button[data-testid="stBaseButton-tertiary"] p,
.stButton button[data-testid="stBaseButton-tertiary"] div,
.stButton button[data-testid="stBaseButton-tertiary"] span { color: var(--ma-muted) !important; }
.stButton button[kind="tertiary"]:hover, .stButton button[data-testid="stBaseButton-tertiary"]:hover {
    background: var(--ma-fill) !important; color: var(--ma-text) !important;
}
.stButton button[kind="tertiary"]:hover p,
.stButton button[kind="tertiary"]:hover div,
.stButton button[kind="tertiary"]:hover span,
.stButton button[data-testid="stBaseButton-tertiary"]:hover p,
.stButton button[data-testid="stBaseButton-tertiary"]:hover div,
.stButton button[data-testid="stBaseButton-tertiary"]:hover span { color: var(--ma-text) !important; }
/* 删除是破坏性操作，平时保持中性灰，悬停才透出红色警示——跟finance-agent
   的删除图标同一个道理，全站仅有的彩色出现在这种"真正该被注意"的地方。 */
[class*="st-key-wb_del_"] button:hover,
[class*="st-key-wb_del_"] button:hover p,
[class*="st-key-wb_del_"] button:hover div,
[class*="st-key-wb_del_"] button:hover span { border-color: var(--ma-danger) !important; color: var(--ma-danger) !important; }

.turn-badge {
    display: inline-block; background: transparent; border: 1px solid var(--ma-border);
    color: var(--ma-muted); padding: 1px 8px; border-radius: var(--ma-radius-sm); font-size: 0.7rem; margin-bottom: 4px;
}
/* Expander/状态框去掉整块底色和圆角边框，改成跟站内其它区块一样的发丝线。 */
[data-testid="stExpander"] details { border: none !important; border-bottom: 1px solid var(--ma-border) !important; border-radius: 0 !important; background: transparent !important; }
[data-testid="stExpander"] summary { padding: 10px 2px !important; }
[data-testid="stExpander"] summary:hover { background: rgba(23,24,28,0.02) !important; }
[data-testid="stStatusWidget"] { background: var(--ma-surface) !important; border: 1px solid var(--ma-border) !important; border-radius: var(--ma-radius) !important; }

pre, code { background: var(--ma-fill) !important; border: 1px solid var(--ma-border) !important; border-radius: var(--ma-radius-sm) !important; font-size: 0.82rem !important; color: var(--ma-text-2) !important; }
hr { border-color: var(--ma-border) !important; }
[data-testid="stSidebar"] hr { margin: 8px 0 !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 6px !important; }

.katex-display { margin: 0.8em 0 !important; overflow-x: auto !important; overflow-y: hidden !important; }
.katex { font-size: 1.05em !important; }
.katex-display > .katex { font-size: 1.1em !important; }
.katex, .katex * { color: var(--ma-text) !important; background: transparent !important; }
.katex svg path, .katex .svg-align path, .katex .delimsizing path, .katex .stretchy path { fill: var(--ma-text) !important; stroke: var(--ma-text) !important; }
mjx-container, mjx-container * { color: var(--ma-text) !important; background: transparent !important; }
mjx-container svg, mjx-container svg * { fill: var(--ma-text) !important; }

[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div { background: var(--ma-surface) !important; border: 1px solid var(--ma-border) !important; border-radius: var(--ma-radius) !important; }
[data-testid="stAudioInput"] button { background: transparent !important; color: var(--ma-muted) !important; width: 72px !important; height: 72px !important; min-width: 72px !important; border-radius: 50% !important; }
[data-testid="stAudioInput"] button svg { width: 36px !important; height: 36px !important; }

[data-testid="stTextArea"] textarea {
    background: var(--ma-surface) !important; border: 1px solid var(--ma-border-2) !important;
    border-radius: var(--ma-radius) !important; color: var(--ma-text) !important;
    font-size: 0.95rem !important; padding: 10px 16px !important; resize: none !important;
}
[data-testid="stTextArea"] textarea:focus { border-color: var(--ma-ink) !important; box-shadow: none !important; }

[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"] { background: transparent !important; border: none !important; padding: 4px 0 !important; }
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploadDropzone"] small { display: none !important; }
[data-testid="stFileUploaderDropzone"] > div > span,
[data-testid="stFileUploadDropzone"] > div > span { display: none !important; }
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: transparent !important; border: 1px solid var(--ma-border) !important;
    border-radius: var(--ma-radius) !important; color: var(--ma-text) !important; width: 100% !important;
    padding: 14px 20px !important; font-size: 0.92rem !important; font-weight: 500 !important; justify-content: center !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover { border-color: var(--ma-border-2) !important; background: var(--ma-fill) !important; }

[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div { background: var(--ma-surface) !important; border: 1px solid var(--ma-border-2) !important; border-radius: var(--ma-radius) !important; color: var(--ma-text) !important; }
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul { background: var(--ma-surface) !important; }
[data-baseweb="menu"] li { color: var(--ma-text) !important; }
[data-baseweb="menu"] li:hover { background: var(--ma-fill) !important; }

[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: var(--ma-text) !important; }

/* 欢迎页功能卡片：去掉阴影上浮，只用边框深浅表达悬停，跟finance-agent
   全站"不做上浮/阴影动效"的克制原则一致。 */
.feature-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 20px 0 12px; }
.feature-card { background: transparent; border-radius: var(--ma-radius); padding: 18px 16px; text-align: left; border: 1px solid var(--ma-border); transition: border-color .15s ease; }
.feature-card:hover { border-color: var(--ma-border-2); }
.feature-title { font-size: 0.92rem; font-weight: 600; color: var(--ma-text) !important; margin-bottom: 5px; }
.feature-desc { font-size: 0.78rem; color: var(--ma-muted) !important; line-height: 1.5; }

button[kind="secondary"][data-testid*="wb_add"] {
    font-size: 0.75rem !important; color: var(--ma-muted) !important;
    border-color: var(--ma-border) !important; padding: 2px 10px !important;
    height: auto !important; min-height: 28px !important; border-radius: 14px !important; background: transparent !important;
}

.login-logo { text-align: center; padding: 60px 0 24px; }
.login-logo-icon { font-size: 3rem; }
.login-logo-title { font-family: 'Source Serif 4', 'Songti SC', STSong, serif !important; font-size: 1.55rem; font-weight: 600; letter-spacing: -0.012em; color: var(--ma-text) !important; margin: 8px 0 4px; }
.login-logo-sub { font-size: 0.85rem; color: var(--ma-muted) !important; }

@media (max-width: 768px) {
    /* 隐藏 Streamlit 原生侧边栏折叠按钮 */
    [data-testid="stSidebarCollapseButton"],
    button[kind="header"] { display: none !important; }

    [data-testid="stSidebar"] {
        display: block !important; position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 82vw !important; max-width: 300px !important; height: 100vh !important;
        z-index: 9998 !important; overflow-y: auto !important;
        transform: translateX(-110%) !important;
        transition: transform 0.26s cubic-bezier(.4,0,.2,1) !important;
        padding-top: 56px !important;
        min-width: 0 !important;
        max-width: 300px !important;
    }
    [data-testid="stSidebar"] > div:first-child { width: auto !important; padding: 6px 12px 12px !important; }
    [data-testid="stSidebar"].ma-sb-open { transform: translateX(0) !important; box-shadow: 6px 0 32px rgba(0,0,0,0.15) !important; }

    [data-testid="stSidebar"] .stButton button {
        font-size: 0.82rem !important; padding: 7px 4px !important;
        min-height: 34px !important; height: auto !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        margin-bottom: 6px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        font-size: 0.84rem !important; padding: 8px 4px !important;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 6px !important; }
    [data-testid="stSidebar"] p { font-size: 0.8rem !important; margin: 0 !important; }

    /* 汉堡按钮改成跟站内图标按钮同一种克制处理：发丝描边，不用重阴影浮块。 */
    #ma-hamburger {
        display: flex !important; position: fixed !important;
        top: 10px !important; left: 10px !important; z-index: 9999 !important;
        width: 40px !important; height: 40px !important;
        background: var(--ma-surface) !important; border: 1px solid var(--ma-border-2) !important;
        border-radius: var(--ma-radius) !important; align-items: center !important; justify-content: center !important;
        cursor: pointer !important; box-shadow: none !important;
        font-size: 1.2rem !important; user-select: none !important; -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop {
        display: none; position: fixed !important; inset: 0 !important;
        background: rgba(23,24,28,0.35) !important; z-index: 9997 !important; -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop.active { display: block !important; }

    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 4px !important; }
    [data-testid="stColumn"] { min-width: 0 !important; flex-shrink: 1 !important; overflow: hidden !important; }
    .bubble-user { max-width: 80vw !important; font-size: 0.9rem !important; }
    [data-testid="stElementContainer"]:has(.asst-bubble-marker) + [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] { font-size: 0.9rem !important; }
    .greeting-main { font-size: 1.4rem !important; }
    .av { width: 28px !important; height: 28px !important; font-size: 0.9rem !important; }
    .app-header-title { font-size: 0.9rem !important; }
    [data-testid="stChatInputTextArea"] { font-size: 0.9rem !important; }
    .feature-card { padding: 14px 12px; }
    .feature-title { font-size: 0.85rem !important; }
    .feature-desc { font-size: 0.72rem !important; }
}
</style>
"""
