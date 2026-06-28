"""
agent.py — 核心 Agent 循环

支持两种模式：
  DeepSeek 模式（默认）：需要 DEEPSEEK_API_KEY 环境变量
  Ollama 本地模式：设置 USE_LOCAL=1 或传入 use_local=True，使用本地 qwen3.5:9b
"""

import os
import json
import base64
from io import BytesIO
import httpx
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool

# macOS 系统代理会被 httpx 自动读取并拦截 localhost 请求，需要显式禁用
_NO_PROXY_CLIENT = httpx.Client(trust_env=False)

MAX_ITERATIONS = 12

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

_SYSTEM = """You are an expert mathematics tutor. Always format math using LaTeX:
- Inline math: $x^2 + 1$
- Display math (centered): $$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$
- Always use $$ for final answers

When given a problem:
- Simple arithmetic: use `calculator` once, answer directly.
- Complex problems: call `step_decomposer` to plan, then `formula_lookup` if needed, then `calculator`.
- For limits: calculator with operation="limit", variable="x->0" format.
- For definite integrals: calculator with operation="definite_integral", expression="f(x), a, b".
- Never calculate mentally — always use calculator tool.
- End response with a clearly marked final answer using $$ $$.

Respond in Chinese. Use LaTeX for ALL mathematical notation."""


VISION_MODELS = {
    "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
    "Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-32B-Thinking",
    "Qwen/Qwen3-VL-8B-Instruct",
}

LOCAL_MODELS = ["phi4-mini", "phi4", "qwen2.5:7b", "qwen2.5:14b", "gemma3:12b"]
DEFAULT_LOCAL_MODEL = "phi4-mini"

CLOUD_PROVIDERS = {
    # 硅基流动视觉模型（拍题用）
    "Qwen/Qwen3-VL-32B-Instruct":   ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-32B-Thinking":   ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-8B-Instruct":    ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    # DeepSeek（文字解题）
    "deepseek-chat":                 ("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    # Gemini（备用）
    "gemini-2.0-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "gemini-2.5-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
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
            self.model = model or "deepseek-chat"
            _, base_url, env_key = CLOUD_PROVIDERS.get(self.model, ("", "https://api.deepseek.com", "DEEPSEEK_API_KEY"))
            self.client = OpenAI(
                api_key=os.environ.get(env_key, ""),
                base_url=base_url,
            )

    @property
    def supports_vision(self) -> bool:
        return self.model in VISION_MODELS

    def solve(self, problem: str, history: list = None, on_tool_call=None, image_bytes: bytes = None) -> str:
        """运行完整的 agentic loop，支持多轮对话历史。

        on_tool_call(name, args, result): 每次工具调用后回调，result=None 表示调用前。
        """
        messages = [{"role": "system", "content": _SYSTEM}]
        if history:
            messages.extend(history)

        # 视觉模式：压缩图片 + 单次直接调用
        if image_bytes and self.supports_vision:
            image_bytes = _compress_image(image_bytes)
            b64 = base64.b64encode(image_bytes).decode()
            prompt = f"请解答图片中的数学题。{problem}" if problem else "请识别并解答图片中所有数学题，给出完整解题过程。"
            messages.append({"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]})
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )

        messages.append({"role": "user", "content": f"请解题：{problem}"})
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

    def solve_stream(self, problem: str, history: list = None, on_tool_call=None, image_bytes: bytes = None):
        """Run full agentic loop, return a stream of the complete answer."""
        result = self.solve(problem, history=history, on_tool_call=on_tool_call, image_bytes=image_bytes)
        # 视觉模式直接返回真实 stream，文字模式返回 fake stream
        if isinstance(result, str):
            return _fake_stream(result)
        return result


def _compress_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """压缩图片，减少 base64 体积。"""
    try:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_size:
            r = max_size / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return image_bytes


def _fake_stream(text: str):
    """Yield text in chunks that mimic the OpenAI streaming response format."""
    class _Delta:
        def __init__(self, c): self.content = c
    class _Choice:
        def __init__(self, c): self.delta = _Delta(c)
    class _Chunk:
        def __init__(self, c): self.choices = [_Choice(c)]

    import re
    for part in re.split(r'(\s+)', text):
        if part:
            yield _Chunk(part)
