"""
agent.py — 核心 Agent 循环

架构要点（面试讲解用）：
  1. 使用 Claude claude-opus-4-8 + adaptive thinking（让模型自行决定思考深度）
  2. 手动 agentic loop：call API → 检查 stop_reason → 执行工具 → 把结果塞回对话 → 重复
  3. stop_reason == "end_turn"  → 模型完成，提取 text block 返回
     stop_reason == "tool_use" → 执行所有工具，拼装 tool_result，继续循环
"""

import anthropic
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "claude-opus-4-8"

_SYSTEM = """You are an expert mathematics tutor. When given a problem:

1. Call `step_decomposer` first to plan the solution approach.
2. Call `formula_lookup` to retrieve relevant formulas when needed.
3. Use `calculator` for ALL numeric and symbolic computation — never compute mentally.
4. Present a clear step-by-step solution that is educational and easy to follow.
5. End with a clearly marked final answer.

Explain reasoning in Chinese; keep mathematical notation in standard form."""


class MathAgent:
    def __init__(self) -> None:
        # SDK 自动从环境变量 ANTHROPIC_API_KEY 读取密钥
        self.client = anthropic.Anthropic()

    def solve(self, problem: str) -> str:
        """对一道数学题运行完整的 agentic loop，返回最终解答文本。"""
        # 对话历史：每轮追加 assistant + user(tool_result) 消息
        messages: list[dict] = [
            {"role": "user", "content": f"请解题：{problem}"}
        ]

        print("\n🤔 Agent 思考中...\n")

        # ── Agentic loop ────────────────────────────────────────────────
        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=8192,
                thinking={"type": "adaptive"},   # 让模型按需开启 extended thinking
                system=_SYSTEM,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # ── 分支 1：模型完成，输出最终答案 ──────────────────────────
            if response.stop_reason == "end_turn":
                return "\n".join(
                    block.text
                    for block in response.content
                    if block.type == "text"
                )

            # ── 分支 2：模型请求调用工具 ─────────────────────────────────
            if response.stop_reason == "tool_use":
                tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

                # 把 assistant 这一轮（含 tool_use blocks）写入历史
                messages.append({"role": "assistant", "content": response.content})

                # 执行所有工具，收集结果
                tool_results = []
                for block in tool_use_blocks:
                    print(f"🔧 调用工具：{block.name}")
                    print(f"   参数：{block.input}")
                    result = execute_tool(block.name, block.input)
                    # 只打印前 120 字，避免刷屏
                    preview = result[:120] + ("…" if len(result) > 120 else "")
                    print(f"   结果：{preview}\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                # 把工具结果作为 user 消息回传给模型，继续循环
                messages.append({"role": "user", "content": tool_results})

            else:
                # 其他 stop_reason（refusal、max_tokens 等）直接终止
                return f"[Agent 停止，原因：{response.stop_reason}]"
