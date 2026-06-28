"""
app.py — Math Agent Web UI (Gradio)

Launch:
  python app.py              # DeepSeek mode (requires DEEPSEEK_API_KEY)
  USE_LOCAL=1 python app.py  # Local Ollama mode — fully offline, no API key needed
"""

import os
import sys
from io import StringIO

import gradio as gr

from agent import MathAgent

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

_agent_cache: dict[bool, MathAgent] = {}


def _get_agent(use_local: bool) -> MathAgent:
    if use_local not in _agent_cache:
        _agent_cache[use_local] = MathAgent(use_local=use_local)
    return _agent_cache[use_local]


def _history_to_agent_fmt(gradio_history: list[dict]) -> list[dict]:
    """Convert Gradio messages list → agent history list."""
    result = []
    for msg in gradio_history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            result.append({"role": role, "content": content})
    return result


def respond(message: str, history: list, use_local: bool):
    """Run the agent and return (answer, tool_trace)."""
    if not message.strip():
        return history, history, "", ""

    agent = _get_agent(use_local)
    agent_history = _history_to_agent_fmt(history)

    # Capture tool-call trace printed to stdout
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        answer = agent.solve(message, history=agent_history)
    except Exception as exc:
        answer = f"❌ 出错：{exc}\n请检查 API Key 或 Ollama 服务是否已启动。"
    finally:
        sys.stdout = old_stdout

    trace = buf.getvalue().strip() or "（无工具调用日志）"

    new_history = history + [
        {"role": "user",      "content": message},
        {"role": "assistant", "content": answer},
    ]
    return new_history, new_history, "", trace


def clear_all(_history):
    return [], [], "", ""


# ── Gradio UI ────────────────────────────────────────────────────────────────

EXAMPLES = [
    ["解方程：2x² + 5x - 3 = 0"],
    ["求导：f(x) = x³·sin(x)"],
    ["计算定积分 ∫₀¹ x² dx（格式：expression=x**2, 0, 1）"],
    ["求极限 lim(x→0) sin(x)/x"],
    ["查公式：复变函数柯西积分公式和留数定理"],
    ["用复化Simpson公式（n=4）估算 ∫₀¹ eˣ dx 的误差上界"],
    ["直角三角形两直角边为 3 和 4，求斜边和三个角"],
    ["解方程组：x + y = 5, x - y = 1"],
]

_CSS = """
#tool-trace textarea { font-family: 'Menlo', 'Monaco', monospace; font-size: 12px; }
.gr-button-primary { background: #6366f1 !important; }
footer { display: none !important; }
"""

with gr.Blocks(title="🧮 Math Solver Agent", css=_CSS, theme=gr.themes.Soft()) as demo:

    gr.Markdown("""
# 🧮 Math Solver Agent

**完全离线的 AI 数学解题系统** — ReAct Agentic Loop · Tool Use · RAG 语义检索 · SymPy 符号计算

基于本地 `qwen3.5:9b`（Ollama），无需 API Key，支持代数、微积分、复变函数、数值分析
""")

    with gr.Row(equal_height=False):

        # ── Left: Chat ──────────────────────────────────────────────────────
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                type="messages",
                label="对话",
                height=460,
                show_copy_button=True,
                avatar_images=(None, "🤖"),
                placeholder="输入数学题，Agent 会自动规划步骤 → 查公式 → 计算...",
            )

            with gr.Row():
                txt = gr.Textbox(
                    placeholder="输入数学题，Enter 发送...",
                    container=False,
                    scale=5,
                    autofocus=True,
                )
                send_btn = gr.Button("发送 ▶", variant="primary", scale=1, min_width=80)
                clear_btn = gr.Button("清空", variant="secondary", scale=1, min_width=60)

            gr.Examples(
                examples=EXAMPLES,
                inputs=[txt],
                label="📝 示例题目（点击填入）",
            )

        # ── Right: Controls + Trace ─────────────────────────────────────────
        with gr.Column(scale=2):
            use_local = gr.Checkbox(
                value=_USE_LOCAL,
                label="🖥️ 本地 Ollama 模式（qwen3.5:9b，完全离线）",
                info="取消勾选则使用 DeepSeek API（需设置 DEEPSEEK_API_KEY 环境变量）",
            )

            gr.Markdown("""
**支持的运算：**
- `evaluate` · `solve` · `differentiate` · `integrate`
- `limit` — 极限，variable 写 `x->0`
- `definite_integral` — 定积分，写 `f(x), a, b`
- `simplify` — 代数化简

**公式库主题：**
algebra · geometry · calculus · trigonometry · statistics · number_theory · **complex_analysis** · **numerical_analysis**
""")

            tool_trace = gr.Textbox(
                label="🔧 Agent 工具调用追踪",
                lines=16,
                max_lines=32,
                interactive=False,
                elem_id="tool-trace",
                placeholder="解题时 Agent 的工具调用日志将在这里实时显示...",
            )

    # ── State + Wiring ────────────────────────────────────────────────────────
    history_state = gr.State([])

    send_btn.click(
        respond,
        inputs=[txt, history_state, use_local],
        outputs=[chatbot, history_state, txt, tool_trace],
    )
    txt.submit(
        respond,
        inputs=[txt, history_state, use_local],
        outputs=[chatbot, history_state, txt, tool_trace],
    )
    clear_btn.click(
        clear_all,
        inputs=[history_state],
        outputs=[chatbot, history_state, txt, tool_trace],
    )


if __name__ == "__main__":
    print("🚀 Starting Math Agent Web UI...")
    print(f"   模式: {'本地 Ollama (qwen3.5:9b)' if _USE_LOCAL else 'DeepSeek API'}")
    print("   访问: http://localhost:7860\n")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
