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
from io import StringIO

import streamlit as st

from agent import MathAgent, LOCAL_MODELS, DEFAULT_LOCAL_MODEL, CLOUD_PROVIDERS

st.set_page_config(
    page_title="🧮 Math Solver Agent",
    page_icon="🧮",
    layout="wide",
)

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"
_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

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


def ocr_math_image(image_bytes: bytes) -> str:
    """用 Gemini 视觉识别图片中的数学题。"""
    if not _GEMINI_KEY:
        return "（未配置 GEMINI_API_KEY，无法识别图片）"
    b64 = base64.b64encode(image_bytes).decode()
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={_GEMINI_KEY}",
            json={"contents": [{"parts": [
                {"text": "请识别图片中的数学题，只输出题目原文，不要解答，不要多余说明"},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}]},
            timeout=15,
        )
        data = resp.json()
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
        selected_model = st.selectbox("云端模型", options=cloud_options, index=0)
        labels = {
            "gemini-2.0-flash": "⚡ 快速，免费额度大",
            "gemini-2.5-flash": "🔥 更强，支持推理",
            "gemini-2.5-pro":   "💎 最强，复杂题首选",
            "deepseek-chat":    "💰 便宜，中文好",
        }
        st.info(labels.get(selected_model, "☁️ 云端模式"))

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

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])
        if msg.get("trace"):
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(msg["trace"], language="text")

# ── 输入区：三 Tab ─────────────────────────────────────────────────────────────
tab_text, tab_camera, tab_upload = st.tabs(["✏️ 文字输入", "📷 拍题", "🖼️ 上传图片"])

user_input = None

with tab_text:
    prefill = st.session_state.pop("prefill", "")
    typed = st.chat_input("输入数学题，例如：解方程 x² - 5x + 6 = 0") or prefill
    if typed:
        user_input = typed

with tab_camera:
    cam_img = st.camera_input("对准题目拍照", key="camera")
    if cam_img:
        with st.spinner("🔍 Gemini 识别中..."):
            extracted = ocr_math_image(cam_img.getvalue())
        st.success(f"识别结果：{extracted}")
        if st.button("✅ 解这道题", key="cam_confirm"):
            user_input = extracted

with tab_upload:
    uploaded = st.file_uploader("上传题目图片", type=["jpg", "jpeg", "png"], key="upload")
    if uploaded:
        st.image(uploaded, width=380)
        with st.spinner("🔍 Gemini 识别中..."):
            extracted_up = ocr_math_image(uploaded.read())
        st.success(f"识别结果：{extracted_up}")
        if st.button("✅ 解这道题", key="up_confirm"):
            user_input = extracted_up

# ── Agent 解题 ─────────────────────────────────────────────────────────────────
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🤖"):
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

            buf = StringIO()
            sys.stdout = buf
            try:
                stream = agent.solve_stream(user_input, history=history, on_tool_call=on_tool_call)
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
                        answer_placeholder.markdown("".join(collected) + "▌")
                answer = "".join(collected)
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
