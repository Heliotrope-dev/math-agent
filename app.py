"""
app.py — Math Agent Web UI (Streamlit)

Launch:
  streamlit run app.py              # DeepSeek mode
  USE_LOCAL=1 streamlit run app.py  # Local Ollama mode (offline)
"""

import os
import sys
from io import StringIO

import streamlit as st

from agent import MathAgent, LOCAL_MODELS, DEFAULT_LOCAL_MODEL, CLOUD_PROVIDERS

st.set_page_config(
    page_title="🧮 Math Solver Agent",
    page_icon="🧮",
    layout="wide",
)

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

EXAMPLES = [
    "解方程：2x² + 5x - 3 = 0",
    "求导：f(x) = x³·sin(x)",
    "计算定积分：x**2, 0, 1（即 ∫₀¹ x² dx）",
    "求极限 lim(x→0) sin(x)/x",
    "查公式：复变函数柯西积分公式和留数定理",
    "用复化Simpson公式（n=4）估算 ∫₀¹ eˣ dx 的误差上界",
    "直角三角形两直角边为 3 和 4，求斜边",
    "解方程组：x + y = 5, x - y = 1",
]


@st.cache_resource
def get_agent(use_local: bool, model: str) -> MathAgent:
    return MathAgent(use_local=use_local, model=model)


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 设置")

    use_local = st.checkbox(
        "🖥️ 本地 Ollama 模式（离线）",
        value=_USE_LOCAL,
        help="使用本地模型，无需 API Key",
    )

    if use_local:
        selected_model = st.selectbox(
            "选择模型",
            options=LOCAL_MODELS,
            index=LOCAL_MODELS.index(DEFAULT_LOCAL_MODEL),
            help="phi4-mini 最快；phi4 最准",
        )
        speed = {"phi4-mini": "⚡ 极快", "phi4": "🐢 较慢但准"}.get(selected_model, "⚡")
        st.success(f"{speed} · 本地离线 · {selected_model}")
    else:
        cloud_options = list(CLOUD_PROVIDERS.keys())
        selected_model = st.selectbox(
            "选择云端模型",
            options=cloud_options,
            index=0,
        )
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
    st.markdown("""
**支持运算**
- evaluate · solve · differentiate · integrate
- `limit` — 极限（variable: `x->0`）
- `definite_integral` — 定积分（`f(x), a, b`）
- simplify

**公式库**
algebra · geometry · calculus · trigonometry
statistics · number_theory
**complex_analysis** · **numerical_analysis**
""")

    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("prefill", None)
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("🧮 Math Solver Agent")
st.caption("完全离线的 AI 数学解题系统 — ReAct Agentic Loop · Tool Use · RAG · SymPy")

# 初始化消息历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史对话
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])
        if msg.get("trace"):
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(msg["trace"], language="text")

# 输入框（优先使用侧边栏点击的示例）
prefill = st.session_state.pop("prefill", "")
user_input = st.chat_input("输入数学题，例如：解方程 x² - 5x + 6 = 0") or prefill

if user_input:
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # 运行 Agent
    with st.chat_message("assistant", avatar="🤖"):
        agent = get_agent(use_local, selected_model or "phi4-mini")
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
            answer_placeholder = st.empty()

            def on_tool_call(name, args, result):
                label = _TOOL_LABELS.get(name, f"🔧 {name}")
                if result is None:
                    status.update(label=f"{label}...")
                    trace_lines.append(f"{label}")
                    trace_lines.append(f"   参数: {args}")
                else:
                    preview = str(result)[:100] + ("…" if len(str(result)) > 100 else "")
                    trace_lines.append(f"   → {preview}\n")

            buf = StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                answer = agent.solve(user_input, history=history, on_tool_call=on_tool_call)
            except Exception as exc:
                answer = f"❌ 出错：{exc}"
            finally:
                sys.stdout = old_stdout

            status.update(label="✅ 完成", state="complete", expanded=False)

        trace = "\n".join(trace_lines) or buf.getvalue().strip()
        st.markdown(answer)
        if trace:
            with st.expander("🔧 工具调用追踪", expanded=False):
                st.code(trace, language="text")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "trace": trace,
    })
