"""
agent.py — 核心 Agent 循环（DeepSeek 版）

DeepSeek 兼容 OpenAI 接口，只需把 base_url 指向 DeepSeek，其余与 OpenAI 完全一致。

与 Ollama 版的区别：
  Ollama:   response.message.tool_calls        arguments 是 dict
  DeepSeek: response.choices[0].message.tool_calls  arguments 是 JSON 字符串，需 json.loads
            tool_result 消息必须带 tool_call_id
"""

import os
import json
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "deepseek-chat"

# DeepSeek 兼容 OpenAI SDK，只改 base_url 和 api_key
client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)

_SYSTEM = """You are an expert mathematics tutor. When given a problem:

- For simple arithmetic (e.g. 1+1, 3×4), just use `calculator` once and give the answer directly.
- For complex problems (equations, calculus, geometry), first call `step_decomposer` to plan,
  then `formula_lookup` if needed, then `calculator` to compute.
- Always use `calculator` for computation — never calculate mentally.
- End with a clearly marked final answer.

Explain reasoning in Chinese; keep mathematical notation in standard form."""


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
            response = client.chat.completions.create(
                model=MODEL,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            # ── 分支 1：没有工具调用 → 返回最终答案 ────────────────────
            if finish_reason != "tool_calls":
                return msg.content

            # ── 分支 2：模型请求调用工具 ─────────────────────────────────
            # 把 assistant 这一轮（含 tool_calls）写入历史
            messages.append(msg)

            for tc in msg.tool_calls:
                name = tc.function.name
                # OpenAI 格式：arguments 是 JSON 字符串，需要解析成 dict
                args = json.loads(tc.function.arguments)

                print(f"🔧 调用工具：{name}")
                print(f"   参数：{args}")

                result = execute_tool(name, args)
                preview = result[:120] + ("…" if len(result) > 120 else "")
                print(f"   结果：{preview}\n")

                # OpenAI 格式要求带 tool_call_id，用于对应是哪次调用的结果
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })
