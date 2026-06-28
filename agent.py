"""
agent.py — 核心 Agent 循环

支持两种模式：
  DeepSeek 模式（默认）：需要 DEEPSEEK_API_KEY 环境变量
  Ollama 本地模式：设置 USE_LOCAL=1 或传入 use_local=True，使用本地 qwen3.5:9b
"""

import os
import json
import httpx
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool

# macOS 系统代理会被 httpx 自动读取并拦截 localhost 请求，需要显式禁用
_NO_PROXY_CLIENT = httpx.Client(trust_env=False)

MAX_ITERATIONS = 12

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

_SYSTEM = """You are an expert mathematics tutor. When given a problem:

- For simple arithmetic (e.g. 1+1, 3×4), just use `calculator` once and give the answer directly.
- For complex problems (equations, calculus, geometry, complex analysis), first call `step_decomposer` to plan,
  then `formula_lookup` if needed, then `calculator` to compute.
- Always use `calculator` for computation — never calculate mentally.
- For limits: use calculator with operation="limit" and variable="x->0" format.
- For definite integrals: use calculator with operation="definite_integral" and expression="f(x), a, b".
- End with a clearly marked final answer.

Explain reasoning in Chinese; keep mathematical notation in standard form."""


LOCAL_MODELS = ["phi4-mini", "phi4", "qwen2.5:7b", "qwen2.5:14b", "gemma3:12b"]
DEFAULT_LOCAL_MODEL = "phi4-mini"

CLOUD_PROVIDERS = {
    "gemini-2.0-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "gemini-2.5-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "gemini-2.5-pro":                ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "deepseek-chat":                 ("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
}


class MathAgent:
    def __init__(self, use_local: bool = _USE_LOCAL, model: str = None):
        self.use_local = use_local
        if use_local:
            self.client = OpenAI(
                api_key="ollama",
                base_url="http://localhost:11434/v1",
                http_client=_NO_PROXY_CLIENT,
            )
            self.model = model or DEFAULT_LOCAL_MODEL
        else:
            self.model = model or "gemini-2.0-flash"
            _, base_url, env_key = CLOUD_PROVIDERS.get(self.model, ("", "https://api.deepseek.com", "DEEPSEEK_API_KEY"))
            self.client = OpenAI(
                api_key=os.environ.get(env_key, ""),
                base_url=base_url,
            )

    def solve(self, problem: str, history: list = None, on_tool_call=None) -> str:
        """运行完整的 agentic loop，支持多轮对话历史。

        on_tool_call(name, args, result): 每次工具调用后回调，result=None 表示调用前。
        """
        messages = [{"role": "system", "content": _SYSTEM}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": f"请解题：{problem}"})

        mode_label = self.model if self.use_local else "DeepSeek"
        print(f"\n🤔 Agent 思考中...（本地 {mode_label}）\n")

        extra = {"think": False} if self.use_local else {}

        for iteration in range(MAX_ITERATIONS):
            response = self.client.chat.completions.create(
                model=self.model,
                tools=TOOL_DEFINITIONS,
                messages=messages,
                extra_body=extra,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason != "tool_calls" or not msg.tool_calls:
                return msg.content or "（无输出）"

            messages.append(msg)

            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                print(f"🔧 调用工具：{name}")
                print(f"   参数：{args}")

                if on_tool_call:
                    on_tool_call(name, args, None)

                result = execute_tool(name, args)
                preview = result[:120] + ("…" if len(result) > 120 else "")
                print(f"   结果：{preview}\n")

                if on_tool_call:
                    on_tool_call(name, args, result)

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })

        return "⚠️ 达到最大迭代次数，请尝试更简单的描述方式。"
