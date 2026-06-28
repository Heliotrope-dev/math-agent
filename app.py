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

from agent import MathAgent, LOCAL_MODELS, DEFAULT_LOCAL_MODEL, CLOUD_PROVIDERS

st.set_page_config(
    page_title="🧮 Math Solver Agent",
    page_icon="🧮",
    layout="wide",
)

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
def get_agent(use_local: bool, model: str) -> MathAgent:
    return MathAgent(use_local=use_local, model=model)


def fix_latex(text: str) -> str:
    """把 DeepSeek/Gemini 输出的 \\[...\\] 和 \\(...\\) 转成 Streamlit 能渲染的 $$...$$ 和 $...$。"""
    import re
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', r'\n$$\1$$\n', text, flags=re.DOTALL)
    text = re.sub(r'\\\(\s*(.*?)\s*\\\)', r'$\1$', text, flags=re.DOTALL)
    return text


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


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 设置")

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
    st.markdown("**📝 示例题目**")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state["prefill"] = ex

    st.divider()
    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("prefill", None)
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🧮 Math Solver Agent")
st.caption("完全离线的 AI 数学解题系统 — ReAct Agentic Loop · Tool Use · RAG · SymPy")

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

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
        content = fix_latex(msg["content"]) if msg["role"] == "assistant" else msg["content"]
        st.markdown(content)
        if msg.get("trace"):
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(msg["trace"], language="text")

# ── 输入区：两 Tab ─────────────────────────────────────────────────────────────
tab_text, tab_photo = st.tabs(["✏️ 文字输入", "📷 拍题 / 上传图片"])

user_input = None

with tab_text:
    prefill = st.session_state.pop("prefill", "")
    typed = st.chat_input("输入数学题，例如：解方程 x² - 5x + 6 = 0") or prefill
    if typed:
        user_input = typed

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
        # agent 先用 selected_model 初始化，拍题时会在下面覆盖为视觉模型
        agent = get_agent(use_local, selected_model)
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

        with st.status("🤔 思考中...", expanded=True) as status:

            def on_tool_call(name, args, result):
                label = _TOOL_LABELS.get(name, f"🔧 {name}")
                if result is None:
                    status.update(label=f"{label}...")
                    trace_lines.append(f"{label}\n   参数: {args}")
                else:
                    preview = str(result)[:100] + ("…" if len(str(result)) > 100 else "")
                    trace_lines.append(f"   → {preview}\n")

            # 取出图片（如果是拍题模式，自动切换视觉模型）
            _img = st.session_state.pop("pending_image", None)
            _solve_model = selected_model
            if _img and _secret("SILICONFLOW_API_KEY"):
                _solve_model = "Qwen/Qwen3-VL-32B-Instruct"
                status.update(label="📷 切换视觉模型中...")
            _agent = get_agent(use_local, _solve_model)

            buf = StringIO()
            sys.stdout = buf
            try:
                stream = _agent.solve_stream(user_input, history=history, on_tool_call=on_tool_call, image_bytes=_img)
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
                answer = fix_latex("".join(collected))
                answer_placeholder.markdown(answer)
            except Exception as e:
                answer = f"❌ 流式输出出错：{e}"
                answer_placeholder.markdown(answer)
        else:
            answer = f"❌ 出错：{err}"
            st.markdown(answer)

        trace = "\n".join(trace_lines) or buf.getvalue().strip()
        if trace:
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(trace, language="text")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "trace": trace,
    })
