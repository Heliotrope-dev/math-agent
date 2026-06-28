"""
app.py — Math Agent Web UI (Streamlit)

Launch:
  streamlit run app.py              # DeepSeek/Gemini 云端
  USE_LOCAL=1 streamlit run app.py  # 本地 Ollama 离线
"""

import os
import sys
import base64
import requests
from io import StringIO, BytesIO
from PIL import Image

import streamlit as st

# 把 Streamlit Cloud secrets 注入环境变量，让 agent.py 正常读取
for _k in ("GEMINI_API_KEY", "DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

import re
from datetime import datetime

from agent import MathAgent, LOCAL_MODELS, DEFAULT_LOCAL_MODEL, CLOUD_PROVIDERS

st.set_page_config(
    page_title="Math Solver Agent",
    page_icon="🧮",
    layout="wide",
)

st.markdown("""
<style>
/* ── 全局字体 ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── 隐藏默认顶栏和底部 ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── 侧边栏 ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
    border-right: 1px solid #2d2d4e;
}
[data-testid="stSidebar"] * { color: #e0e0f0 !important; }
[data-testid="stSidebar"] .stButton button {
    background: #1e1e3a !important;
    border: 1px solid #3d3d6e !important;
    color: #b0b0d0 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    transition: all 0.2s;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #2d2d5e !important;
    border-color: #6c6ccc !important;
    color: #fff !important;
}

/* ── 主标题渐变 ── */
.hero-title {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.4rem;
    font-weight: 700;
    margin-bottom: 0;
    line-height: 1.2;
    text-align: center;
}
.hero-sub {
    color: #888;
    font-size: 0.85rem;
    margin-top: 4px;
    margin-bottom: 1.2rem;
    text-align: center;
}

/* ── 标签页 ── */
[data-testid="stTabs"] button {
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    border-radius: 8px 8px 0 0 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #764ba2 !important;
    border-bottom: 2px solid #764ba2 !important;
}

/* ── 聊天气泡 ── */
[data-testid="stChatMessage"] {
    border-radius: 16px !important;
    padding: 12px 16px !important;
    margin-bottom: 8px !important;
}

/* ── 主按钮 ── */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: opacity 0.2s !important;
}
.stButton button[kind="primary"]:hover { opacity: 0.88 !important; }

/* ── 输入框 ── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: 10px !important;
    border: 1px solid #3d3d6e !important;
    background: #12121f !important;
    color: #e0e0f0 !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #764ba2 !important;
    box-shadow: 0 0 0 2px rgba(118,75,162,0.2) !important;
}

/* ── expander ── */
[data-testid="stExpander"] {
    border: 1px solid #2d2d4e !important;
    border-radius: 10px !important;
    background: #0f0f1a !important;
}

/* ── success/info/warning 卡片 ── */
[data-testid="stAlert"] { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

def _secret(key: str) -> str:
    """从 st.secrets（Streamlit Cloud）或环境变量读取密钥。"""
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

_GEMINI_KEY = _secret("GEMINI_API_KEY")

EXAMPLES = [
    "解方程：2x² + 5x - 3 = 0",
    "求导：f(x) = x³·sin(x)",
    "计算定积分 ∫₀¹ x² dx",
    "求极限 lim(x→0) sin(x)/x",
    "查公式：复变函数柯西积分公式",
    "用复化Simpson公式（n=4）估算 ∫₀¹ eˣ dx 的误差",
    "直角三角形两直角边为 3 和 4，求斜边",
]


@st.cache_resource
def get_agent(use_local: bool, model: str, guide_mode: bool = False) -> MathAgent:
    return MathAgent(use_local=use_local, model=model, guide_mode=guide_mode)


def fix_latex(text: str) -> str:
    """把 \\[...\\] 和 \\(...\\) 转成 Streamlit 能渲染的 $$...$$ 和 $...$。"""
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', r'\n$$\1$$\n', text, flags=re.DOTALL)
    text = re.sub(r'\\\(\s*(.*?)\s*\\\)', r'$\1$', text, flags=re.DOTALL)
    return text


def extract_tags(text: str) -> tuple[str, list[str]]:
    """从回答末尾提取知识点标签行，返回 (去掉标签行的文本, 标签列表)。"""
    match = re.search(r'📚\s*\*{0,2}知识点\*{0,2}\s*[：:](.*?)$', text, re.MULTILINE)
    if not match:
        return text, []
    tags_str = match.group(1).strip()
    tags = [t.strip() for t in re.split(r'[·・,，、]+', tags_str) if t.strip()]
    clean = text[:match.start()].rstrip()
    return clean, tags


def render_tags(tags: list[str], prefix: str = ""):
    if not tags:
        return
    pills = "".join(
        f'<span style="display:inline-block;background:#667eea33;'
        f'border:1px solid #667eea88;color:#6060cc;padding:2px 10px;border-radius:12px;'
        f'font-size:0.78rem;margin:2px 4px 2px 0;font-weight:500;">{t}</span>'
        for t in tags
    )
    st.markdown(
        f'<div style="margin-top:6px;line-height:2.2;">📚 {pills}</div>',
        unsafe_allow_html=True,
    )


def _compress_image(image_bytes: bytes, max_size: int = 800) -> bytes:
    """压缩图片到 max_size px 以内，减少上传体积。"""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def ocr_math_image(image_bytes: bytes) -> str:
    """用 Gemini 视觉识别图片中的数学题。"""
    key = _secret("GEMINI_API_KEY")
    if not key:
        return "（未配置 GEMINI_API_KEY，无法识别图片）"
    try:
        compressed = _compress_image(image_bytes)
        b64 = base64.b64encode(compressed).decode()
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            json={"contents": [{"parts": [
                {"text": "请识别图片中的数学题，只输出题目原文，不要解答，不要多余说明"},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}]},
            timeout=20,
        )
        data = resp.json()
        if "candidates" not in data:
            err = data.get("error", {})
            return f"识别失败：{err.get('message', str(data))}"
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"识别失败：{e}"


# ── Session state 初始化（必须在 sidebar 之前）────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "wrong_book" not in st.session_state:
    st.session_state.wrong_book = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 设置")

    use_local = st.checkbox(
        "🖥️ 本地 Ollama 模式（离线）",
        value=_USE_LOCAL,
        help="使用本地模型，无需 API Key",
    )

    if use_local:
        selected_model = st.selectbox(
            "本地模型",
            options=LOCAL_MODELS,
            index=LOCAL_MODELS.index(DEFAULT_LOCAL_MODEL),
        )
        speed = {"phi4-mini": "⚡ 极快", "phi4": "🐢 较慢但准"}.get(selected_model, "⚡")
        st.success(f"{speed} · 本地离线 · {selected_model}")
    else:
        cloud_options = list(CLOUD_PROVIDERS.keys())
        selected_model = st.selectbox("云端模型", options=cloud_options, index=cloud_options.index("deepseek-chat"))
        labels = {
            "Qwen/Qwen3-VL-32B-Instruct":   "📷 拍题首选 · 看图解题（硅基流动）",
            "Qwen/Qwen3-VL-8B-Instruct":    "📷 拍题轻量版 · 速度更快（硅基流动）",
            "deepseek-chat":                 "💬 文字解题 · 默认推荐",
            "gemini-2.0-flash":              "⚡ 备用",
            "gemini-2.5-flash":              "🔥 备用（更强）",
        }
        st.info(labels.get(selected_model, "☁️ 云端模式"))

    # 动态读取（支持 Streamlit Cloud secrets 热更新）
    gemini_ok = bool(_secret("GEMINI_API_KEY"))
    if not gemini_ok:
        st.warning("未配置 GEMINI_API_KEY，拍题识别不可用")

    st.divider()
    st.markdown("**🎓 解题模式**")
    guide_mode = st.toggle(
        "引导解题（苏格拉底式）",
        value=False,
        help="开启后 AI 不直接给答案，而是逐步引导你思考",
    )
    if guide_mode:
        st.info("💡 引导模式：AI 会给提示，引导你自主解题")
    else:
        st.caption("直接模式：给出完整解题过程")

    st.divider()
    st.markdown("**📝 示例题目**")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["prefill"] = ex

    st.divider()
    # 错题本
    wrong_book = st.session_state.get("wrong_book", [])
    wb_label = f"📓 错题本（{len(wrong_book)} 题）" if wrong_book else "📓 错题本（空）"
    with st.expander(wb_label, expanded=False):
        if not wrong_book:
            st.caption("解完题后点「加入错题本」保存")
        else:
            for wi, wp in enumerate(wrong_book):
                st.markdown(f"**{wi+1}.** {wp['question'][:60]}{'…' if len(wp['question']) > 60 else ''}")
                if wp.get("tags"):
                    render_tags(wp["tags"])
                st.caption(wp.get("saved_at", ""))
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("重新解题", key=f"wb_redo_{wi}", use_container_width=True):
                        st.session_state["prefill"] = wp["question"]
                        st.rerun()
                with c2:
                    if st.button("删除", key=f"wb_del_{wi}", use_container_width=True):
                        st.session_state["wrong_book"].pop(wi)
                        st.rerun()
                st.divider()

    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("prefill", None)
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-title">🧮 Math Solver Agent</div>
<div class="hero-sub">AI 数学解题助手 · 支持拍题 · ReAct Agentic Loop · Tool Use · SymPy</div>
""", unsafe_allow_html=True)

# 手机端模型快速切换（桌面端用侧边栏，手机端用这里）
with st.expander("⚙️ 切换模型", expanded=False):
    _cloud_opts = list(CLOUD_PROVIDERS.keys())
    _labels = {
        "gemini-2.0-flash": "⚡ Gemini 2.0 Flash（默认，快）",
        "gemini-2.5-flash": "🔥 Gemini 2.5 Flash（更强）",
        "gemini-2.5-pro":   "💎 Gemini 2.5 Pro（最强）",
        "deepseek-chat":    "💰 DeepSeek V3（便宜）",
    }
    _mobile_model = st.selectbox(
        "云端模型",
        options=_cloud_opts,
        index=_cloud_opts.index(selected_model) if selected_model in _cloud_opts else 0,
        format_func=lambda x: _labels.get(x, x),
        key="mobile_model",
        label_visibility="collapsed",
    )
    if not use_local:
        selected_model = _mobile_model

for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
        content = fix_latex(msg["content"]) if msg["role"] == "assistant" else msg["content"]
        st.markdown(content)
        if msg["role"] == "assistant":
            if msg.get("tags"):
                render_tags(msg["tags"])
            if msg.get("trace"):
                with st.expander("🔧 工具调用追踪", expanded=False):
                    st.code(msg["trace"], language="text")
            # 操作按钮（只对已有内容的历史消息显示）
            prev_q = st.session_state.messages[i - 1]["content"] if i > 0 else ""
            bcol1, bcol2, _ = st.columns([1, 1, 3])
            with bcol1:
                if st.button("🎯 举一反三", key=f"similar_{i}", use_container_width=True):
                    st.session_state["_similar"] = {"question": prev_q, "answer": msg["content"][:400]}
            with bcol2:
                already_saved = any(
                    wp["question"] == prev_q for wp in st.session_state.wrong_book
                )
                btn_label = "✅ 已加入" if already_saved else "📖 加入错题本"
                if st.button(btn_label, key=f"wrongbook_{i}", use_container_width=True, disabled=already_saved):
                    st.session_state.wrong_book.append({
                        "question": prev_q,
                        "answer": msg["content"],
                        "tags": msg.get("tags", []),
                        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.rerun()
        elif msg.get("trace"):
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(msg["trace"], language="text")

# ── 举一反三触发 ────────────────────────────────────────────────────────────────
_similar_ctx = st.session_state.pop("_similar", None)

# ── 输入区：两 Tab ─────────────────────────────────────────────────────────────
tab_text, tab_photo = st.tabs(["✏️ 文字输入", "📷 拍题 / 上传图片"])

user_input = None

with tab_text:
    prefill = st.session_state.pop("prefill", "")
    typed = st.chat_input("输入数学题，例如：解方程 x² - 5x + 6 = 0") or prefill
    if typed:
        user_input = typed

# 举一反三作为新一轮对话触发
if _similar_ctx and not user_input:
    user_input = "🎯 举一反三"
    st.session_state["_similar_ctx_data"] = _similar_ctx

with tab_photo:
    st.caption("拍照或上传图片后，手动输入题目内容发给 AI 解题")
    photo_file = st.file_uploader(
        "选择或拍摄题目图片",
        type=["jpg", "jpeg", "png"],
        key="photo",
        label_visibility="collapsed",
    )
    if photo_file:
        img_bytes = photo_file.read()
        st.image(img_bytes, width=360)

        _has_vision_key = bool(_secret("SILICONFLOW_API_KEY"))
        if _has_vision_key:
            st.success("📷 自动切换视觉模型解题")
        else:
            st.info("请手动输入题目（未配置视觉模型 Key）")

        photo_note = st.text_input(
            "说明（可选）",
            placeholder="例如：只解第3题 / 第6题用行列式方法",
            key="photo_note",
        )

        if not _has_vision_key:
            photo_question = st.text_area(
                "题目内容",
                height=100,
                placeholder="对照图片手动输入题目内容",
                key="photo_question",
            )
        else:
            photo_question = ""

        _can_submit = _has_vision_key or bool(photo_question.strip() if not _has_vision_key else True)
        if st.button("✅ 解这道题", key="photo_confirm", type="primary", disabled=not _can_submit):
            if _has_vision_key:
                st.session_state["pending_image"] = img_bytes
                user_input = photo_note.strip() or "请解答图片中的数学题"
            else:
                final_q = photo_question.strip()
                if photo_note.strip():
                    final_q += "\n" + photo_note.strip()
                user_input = final_q

# ── Agent 解题 ─────────────────────────────────────────────────────────────────
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🤖"):
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        trace_lines: list[str] = []
        _TOOL_LABELS = {
            "step_decomposer": "📋 规划解题步骤",
            "formula_lookup":  "📐 检索公式",
            "calculator":      "🔢 符号计算",
        }

        # 举一反三：构造特殊提示，不使用历史（避免混入当前对话）
        _sim_data = st.session_state.pop("_similar_ctx_data", None)
        if _sim_data:
            solve_input = (
                f"上一道题目是：{_sim_data['question']}\n\n"
                "请出一道与上题类似但不同的练习题，标注题型和难度，只出题，不要给解答。"
            )
            solve_history = []
        else:
            solve_input = user_input
            solve_history = history

        with st.status("🤔 思考中...", expanded=True) as status:
            if guide_mode:
                status.update(label="💡 引导模式 - 组织提示...")

            def on_tool_call(name, args, result):
                label = _TOOL_LABELS.get(name, f"🔧 {name}")
                if result is None:
                    status.update(label=f"{label}...")
                    trace_lines.append(f"{label}\n   参数: {args}")
                else:
                    preview = str(result)[:100] + ("…" if len(str(result)) > 100 else "")
                    trace_lines.append(f"   → {preview}\n")

            # 取出图片（拍题模式自动切换视觉模型）
            _img = st.session_state.pop("pending_image", None)
            _solve_model = selected_model
            _use_guide = guide_mode and not _img  # 视觉模式不走引导流程
            if _img and _secret("SILICONFLOW_API_KEY"):
                _solve_model = "Qwen/Qwen3-VL-30B-A3B-Instruct"
                status.update(label="📷 切换视觉模型中...")
            # 举一反三也不需要引导模式（直接出题）
            if _sim_data:
                _use_guide = False
            _agent = get_agent(use_local, _solve_model, guide_mode=_use_guide)

            buf = StringIO()
            sys.stdout = buf
            try:
                stream = _agent.solve_stream(
                    solve_input,
                    history=solve_history,
                    on_tool_call=on_tool_call,
                    image_bytes=_img,
                )
                err = None
            except Exception as exc:
                stream = None
                err = str(exc)
            finally:
                sys.stdout = sys.__stdout__

            status.update(label="✅ 完成", state="complete", expanded=False)

        if stream is not None:
            answer_placeholder = st.empty()
            collected = []
            try:
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        collected.append(delta)
                        answer_placeholder.markdown(fix_latex("".join(collected)) + "▌")
                raw_answer = "".join(collected)
                clean_answer, tags = extract_tags(raw_answer)
                answer = fix_latex(clean_answer)
                answer_placeholder.markdown(answer)
                render_tags(tags)
            except Exception as e:
                answer = f"❌ 流式输出出错：{e}"
                tags = []
                answer_placeholder.markdown(answer)
        else:
            answer = f"❌ 出错：{err}"
            tags = []
            st.markdown(answer)

        trace = "\n".join(trace_lines) or buf.getvalue().strip()
        if trace:
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(trace, language="text")

        # 操作按钮（当前回答）
        prev_q = st.session_state.messages[-1]["content"] if st.session_state.messages else ""
        bcol1, bcol2, _ = st.columns([1, 1, 3])
        with bcol1:
            if st.button("🎯 举一反三", key="similar_new", use_container_width=True):
                st.session_state["_similar"] = {"question": prev_q, "answer": answer[:400]}
                st.rerun()
        with bcol2:
            if st.button("📖 加入错题本", key="wrongbook_new", use_container_width=True):
                st.session_state.wrong_book.append({
                    "question": prev_q,
                    "answer": answer,
                    "tags": tags,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                st.rerun()

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "tags": tags,
        "trace": trace,
    })
