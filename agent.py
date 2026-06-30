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
# 注：不能在模块级别共享 httpx.Client，每个 agent 实例单独创建避免连接池冲突

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"
_DEFAULT_MAX_ITERATIONS = 12
_MAX_HISTORY_TURNS = 10  # 保留最近 N 轮对话（user+assistant 算一轮）

_SYSTEM = """你是一位专业的数学教师。

解题规则：
- 简单算术：直接调用 calculator 工具，给出答案
- 复杂题：先 step_decomposer 规划，再 formula_lookup 查公式，最后 calculator 计算
- 极限：calculator 的 operation="limit"，variable="x->0"
- 定积分：calculator 的 operation="definite_integral"，expression="f(x), a, b"
- 绝不心算，必须调用工具
- 最后用 $$ ... $$ 标注最终答案

格式要求：
- 行内公式：$...$
- 独立公式：$$ ... $$
- 回复中文

解题完成后，按顺序输出两行：
📚 知识点：知识点1 · 知识点2 · 知识点3
🧪 例题：[一道与本题同类型、难度相近的练习题，用一行写完，不给答案]"""

_GUIDE_SYSTEM = """你是一位耐心的数学家教，使用苏格拉底式引导法。

教学方式：
- 先识别题型，指出解题方向（不直接给完整答案）
- 给出第一个提示，引导学生自己思考
- 根据学生的回应，逐步揭示下一步
- 最终当学生理解后，给出完整总结

格式要求：
- 行内公式：$...$
- 独立公式：$$ ... $$
- 回复中文

每次回复最后单独一行写：
📚 知识点：知识点1 · 知识点2 · 知识点3"""


VISION_MODELS = {
    "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro",
    "Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-32B-Thinking",
    "Qwen/Qwen3-VL-30B-A3B-Instruct",
    "Qwen/Qwen3-VL-8B-Instruct",
}

LOCAL_MODELS = ["phi4-mini", "phi4", "qwen2.5:7b", "qwen2.5:14b", "gemma3:12b"]
DEFAULT_LOCAL_MODEL = "phi4-mini"

CLOUD_PROVIDERS = {
    # 硅基流动视觉模型（拍题用）
    "Qwen/Qwen3-VL-30B-A3B-Instruct": ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-32B-Instruct":     ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-32B-Thinking":     ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-8B-Instruct":      ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    # DeepSeek（文字解题）
    "deepseek-chat":                 ("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    # Gemini（备用）
    "gemini-2.0-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "gemini-2.5-flash":              ("google", "https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
}


class MathAgent:
    def __init__(
        self,
        use_local: bool = _USE_LOCAL,
        model: str = None,
        guide_mode: bool = False,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ):
        self.use_local = use_local
        self.guide_mode = guide_mode
        self.max_iterations = max_iterations
        if use_local:
            self.client = OpenAI(
                api_key="ollama",
                base_url="http://127.0.0.1:11434/v1",
                # trust_env=False 绕过 macOS 系统代理
                # max_keepalive_connections=0 禁用连接复用，避免 Ollama 关闭连接后再请求报错
                http_client=httpx.Client(
                    trust_env=False,
                    limits=httpx.Limits(max_keepalive_connections=0, max_connections=100),
                ),
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

    @staticmethod
    def _trim_history(history: list) -> list:
        """保留最近 _MAX_HISTORY_TURNS 轮（每轮 = user + assistant），避免 context 过长。"""
        turns = []
        buf = []
        for msg in reversed(history):
            buf.insert(0, msg)
            if msg["role"] == "user":
                turns.insert(0, buf)
                buf = []
                if len(turns) >= _MAX_HISTORY_TURNS:
                    break
        return [m for turn in turns for m in turn]

    def solve(self, problem: str, history: list = None, on_tool_call=None, image_bytes: bytes = None) -> str:
        """运行完整的 agentic loop，支持多轮对话历史。

        on_tool_call(name, args, result): 每次工具调用后回调，result=None 表示调用前。
        """
        system = _GUIDE_SYSTEM if self.guide_mode else _SYSTEM
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(self._trim_history(history))

        # 视觉模式：压缩图片（减少 token）+ 单次直接调用
        if image_bytes and self.supports_vision:
            image_bytes = _compress_image(image_bytes, max_size=768)
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
                max_tokens=4096,
            )

        # 引导模式：无工具调用，直接流式对话
        if self.guide_mode:
            messages.append({"role": "user", "content": problem})
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=2048,
            )

        messages.append({"role": "user", "content": f"请解题：{problem}"})
        extra = {}  # think:False 会导致 Ollama 挂起，去掉

        for iteration in range(self.max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                tools=TOOL_DEFINITIONS,
                messages=messages,
                max_tokens=4096,
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


def _compress_image(image_bytes: bytes, max_size: int = 768) -> bytes:
    """压缩图片，减少图片 token 数量。"""
    try:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_size:
            r = max_size / max(w, h)
            img = img.resize((int(w * r), int(h * r)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("图片压缩失败，使用原图：%s", e)
        return image_bytes


def _fake_stream(text: str, chunk_size: int = 10):
    """Yield text in fixed-size chunks that mimic the OpenAI streaming response format."""
    class _Delta:
        def __init__(self, c): self.content = c
    class _Choice:
        def __init__(self, c): self.delta = _Delta(c)
    class _Chunk:
        def __init__(self, c): self.choices = [_Choice(c)]

    for i in range(0, len(text), chunk_size):
        yield _Chunk(text[i:i + chunk_size])
