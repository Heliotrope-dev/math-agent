"""
agent.py — 核心 Agent 循环（Ollama 版）

与 Anthropic 版的区别（面试对比讲解用）：
  Anthropic: stop_reason == "tool_use" / "end_turn"
  Ollama:    response.message.tool_calls 有值 / 为空

其他架构完全一致：手动 agentic loop，工具分发，对话历史追加。
"""

import ollama
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "qwen3:14b"

_SYSTEM = """You are an expert mathematics tutor. When given a problem:

1. Call `step_decomposer` first to plan the solution approach.
2. Call `formula_lookup` to retrieve relevant formulas when needed.
3. Use `calculator` for ALL numeric and symbolic computation — never compute mentally.
4. Present a clear step-by-step solution that is educational and easy to follow.
5. End with a clearly marked final answer.

Explain reasoning in Chinese; keep mathematical notation in standard form.
/no_think"""


class MathAgent:
    def solve(self, problem: str) -> str:
        """对一道数学题运行完整的 agentic loop，返回最终解答文本。"""
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": f"请解题：{problem}"},
        ]

        print("\n🤔 Agent 思考中...\n")

        # ── Agentic loop ────────────────────────────────────────────────
        while True:
            response = ollama.chat(
                model=MODEL,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            msg = response.message

            # ── 分支 1：没有工具调用 → 模型完成，返回最终答案 ──────────
            if not msg.tool_calls:
                return msg.content

            # ── 分支 2：模型请求调用工具 ─────────────────────────────────
            # 把 assistant 这一轮（含 tool_calls）写入历史
            messages.append(msg)

            # 执行每个工具，逐条追加 tool 消息
            for call in msg.tool_calls:
                name = call.function.name
                args = call.function.arguments   # dict，Ollama 已自动解析 JSON

                print(f"🔧 调用工具：{name}")
                print(f"   参数：{args}")

                result = execute_tool(name, args)
                preview = result[:120] + ("…" if len(result) > 120 else "")
                print(f"   结果：{preview}\n")

                messages.append({
                    "role":    "tool",
                    "name":    name,
                    "content": result,
                })
            # 继续循环，把工具结果交还给模型
