"""
agent.py — Core Agent Loop

Two modes:
  DeepSeek (default): requires DEEPSEEK_API_KEY env var
  Ollama local: set USE_LOCAL=1 or pass use_local=True, uses local qwen3.5:9b
"""

import os
import json
import base64
from io import BytesIO
import httpx
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool

# macOS system proxy is auto-detected by httpx and blocks localhost; disable explicitly
# NOTE: Do not share httpx.Client at module level; create per-instance to avoid pool conflicts

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"
_DEFAULT_MAX_ITERATIONS = 20
_MAX_HISTORY_TURNS = 10  # keep last N turns (user+assistant = 1 turn)

_SYSTEM = """你是一位大学数学课本风格的助教，行文严谨清晰。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★ 模式一：知识讲解
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
触发：消息中含有"【知识点讲解】"

⚠️ 收到知识讲解请求时，禁止直接解算具体题目，禁止输出"解："或"答案："。
必须按照以下四步结构输出，不得跳步：

**第一步 · 概念梳理**
用课本语言讲清楚这个知识点"是什么、为什么"，给出严格定义和直觉理解（100～200字）。

**第二步 · 核心方法**
列出 2～3 个最重要的定理/公式/技巧，逐条说明适用场景。

**第三步 · 例题精讲（由易到难）**
自拟两道例题，不得直接解算外部题目：
- 【基础例】简单入门题，完整解题步骤，让读者看懂基本流程
- 【进阶例】有一定难度，结合前面方法，展示综合运用

**第四步 · 易错提醒**
列出 1～2 个常见错误：❌ 错误做法 → ✅ 正确做法

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★ 模式二：解题
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
触发：消息以"请解题："开头，或用户明确给出一道题要求"求/算/解/证明/讲解"

⚠️ 禁止只给最终答案，必须给出完整解析过程：
1. 用 step_decomposer 规划解题思路
2. 用 formula_lookup 查所需公式/定理
3. 逐步推导，每步编号，用 calculator 计算具体数值
4. 最终答案单独成行：$$ ... $$
5. 末尾附：📚 知识点：… 和 🧪 例题：…

用户说"讲解一下"时，结合上下文解释这道题的完整解题过程和思路，不重复题目。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★ 模式三：闲聊
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
问候/非数学问题，友好简短回答。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
格式规则（所有模式适用）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 行内公式 $...$，独立公式 $$ ... $$
- 教材口吻，定义/定理/步骤分层清晰
- 全程中文
- 涉及函数图像/几何曲线：调用 plot_function"""

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
    "Qwen/Qwen3-VL-32B-Instruct", "Qwen/Qwen3-VL-32B-Thinking",
    "Qwen/Qwen3-VL-30B-A3B-Instruct",
    "Qwen/Qwen3-VL-8B-Instruct",
}

LOCAL_MODELS = ["phi4-mini", "phi4"]
DEFAULT_LOCAL_MODEL = os.environ.get("MATH_AGENT_MODEL", "qwen3.5:9b")

CLOUD_PROVIDERS = {
    # 硅基流动视觉模型（拍题用）
    "Qwen/Qwen3-VL-30B-A3B-Instruct": ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-32B-Instruct":     ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-32B-Thinking":     ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "Qwen/Qwen3-VL-8B-Instruct":      ("siliconflow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    # DeepSeek（文字解题）
    "deepseek-chat":                 ("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
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
        self._own_client = False
        if use_local:
            _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1"
            self.client = OpenAI(
                api_key="ollama",
                base_url=_ollama_url,
                http_client=httpx.Client(
                    trust_env=False,
                    verify=False,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=100),
                ),
            )
            self._own_client = True
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

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
        self._own_client = False

    @staticmethod
    def _trim_history(history: list) -> list:
        """Keep last _MAX_HISTORY_TURNS turns (each = user + assistant) to avoid context overflow."""
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

        # vision mode: compress image (reduce tokens) + single direct call
        if image_bytes and self.supports_vision:
            image_bytes = _compress_image(image_bytes, max_size=768)
            b64 = base64.b64encode(image_bytes).decode()
            _default_prompt = "请解答图片中的数学题"
            if problem and problem.strip() != _default_prompt:
                prompt = (
                    f"图片中有多道数学题。请只找到并解答用户指定的题目：{problem}\n"
                    "要求：给出完整解题步骤和最终答案，用 $$ ... $$ 标注最终答案，不要解答其他题目。"
                )
            else:
                prompt = "请识别并解答图片中所有数学题，给出完整解题过程和最终答案。"
            messages.append({"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]})
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=8192,
            )

        # guide mode: no tool calls, direct streaming conversation
        if self.guide_mode:
            messages.append({"role": "user", "content": problem})
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=2048,
            )

        # only "【知识点讲解】" prefix from app enters explain mode
        # plain "讲解一下"/"介绍一下" is solving context, follows normal flow
        is_explain = problem.lstrip().startswith("【知识点讲解】")
        messages.append({"role": "user", "content": problem if is_explain else f"请解题：{problem}"})
        extra = {}  # think:False 会导致 Ollama 挂起，去掉

        # explain mode: only calculator tool, no draw_mindmap/plot_function
        # prevent AI from calling viz tools early and breaking the 5-section structure
        _EXPLAIN_TOOLS = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == "calculator"]
        _tools_supported = True

        # accumulate text from tool-calling rounds to avoid loss
        _accumulated: list[str] = []

        for iteration in range(self.max_iterations):
            _active_tools = (_EXPLAIN_TOOLS if is_explain else TOOL_DEFINITIONS) if _tools_supported else None
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    tools=_active_tools,
                    messages=messages,
                    max_tokens=8192,
                    extra_body=extra,
                )
            except Exception as e:
                err = str(e).lower()
                if _tools_supported and ("tool" in err or "function" in err
                                         or "400" in err or "bad request" in err
                                         or "502" in err):
                    _tools_supported = False
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=8192,
                        extra_body=extra,
                    )
                else:
                    raise

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason != "tool_calls" or not msg.tool_calls:
                # final reply: prepend accumulated text from earlier rounds
                final = msg.content or "（无输出）"
                if _accumulated:
                    final = "\n\n".join(_accumulated) + "\n\n" + final
                return final

            # tool-calling round: save same-round text (next call would overwrite)
            if msg.content:
                _accumulated.append(msg.content)

            messages.append(msg)

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    # model sometimes appends junk after JSON; raw_decode for first valid object
                    try:
                        args, _ = json.JSONDecoder().raw_decode(tc.function.arguments.strip())
                    except Exception:
                        args = {}

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

        # iteration limit: ask model to give final answer based on accumulated results
        messages.append({"role": "user", "content": "请根据上面的计算结果，直接给出最终答案，不要再调用工具。"})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=2048,
            )
            return resp.choices[0].message.content or "（无输出）"
        except Exception:
            return "⚠️ 解题超时，请尝试把题目拆分成更小的步骤发送。"

    def solve_stream(self, problem: str, history: list = None, on_tool_call=None, image_bytes: bytes = None):
        """Run the full agentic loop, returning an iterable stream object (real streaming for vision/guide)."""
        result = self.solve(problem, history=history, on_tool_call=on_tool_call, image_bytes=image_bytes)
        if isinstance(result, str):
            return _fake_stream(result)
        return result


def _compress_image(image_bytes: bytes, max_size: int = 768) -> bytes:
    """Compress image to reduce token count."""
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
