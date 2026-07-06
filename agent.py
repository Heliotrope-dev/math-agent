"""
agent.py — Core Agent Loop

Two modes:
  DeepSeek (default): requires DEEPSEEK_API_KEY env var
  Ollama local: set USE_LOCAL=1 or pass use_local=True, uses local qwen3.5:9b
"""

import os
import re
import json
import time
import base64
import logging
from typing import Callable, Iterator, Optional, Union
import httpx

_log = logging.getLogger(__name__)
from openai import (
    OpenAI,
    BadRequestError, RateLimitError, APITimeoutError,
    APIConnectionError, InternalServerError,
)
from tools import TOOL_DEFINITIONS, execute_tool, compress_image

# macOS system proxy is auto-detected by httpx and blocks localhost; disable explicitly

_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"
_DEFAULT_MAX_ITERATIONS = 20
_MAX_HISTORY_TURNS = 10       # keep last N turns (user+assistant = 1 turn)
_CTX_BUDGET_CHARS = 100_000   # ~50K tokens, leaves headroom under 64K context limit
_MAX_MSG_CHARS = 16_000        # single message hard cap before API call
_MAX_TOOL_RESULT_CHARS = 4_000 # tool result truncation to avoid context bloat

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

# ── 智能模型路由 ──────────────────────────────────────────────────────────────
_DEFAULT_VISION_MODEL = "Qwen/Qwen3-VL-30B-A3B-Instruct"
def route_model(problem: str, image_bytes: Optional[bytes] = None,
                default: str = "deepseek-chat") -> str:
    """有图 → 视觉模型；纯文字 → deepseek-chat。"""
    has_sf = bool(os.environ.get("SILICONFLOW_API_KEY"))
    if image_bytes:
        return _DEFAULT_VISION_MODEL if has_sf else default
    return default


class MathAgent:
    def __init__(
        self,
        use_local: bool = _USE_LOCAL,
        model: Optional[str] = None,
        guide_mode: bool = False,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.use_local = use_local
        self.guide_mode = guide_mode
        self.max_iterations = max_iterations
        if use_local:
            _ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/v1"
            # only disable TLS verification for localhost; remote Ollama should use TLS
            _is_local_url = "127.0.0.1" in _ollama_url or "localhost" in _ollama_url
            self.client = OpenAI(
                api_key="ollama",
                base_url=_ollama_url,
                http_client=httpx.Client(
                    trust_env=False,
                    verify=not _is_local_url,
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=100),
                ),
            )
            self.model = model or DEFAULT_LOCAL_MODEL
        else:
            self.model = model or "deepseek-chat"
            _, base_url, env_key = CLOUD_PROVIDERS.get(self.model, ("", "https://api.deepseek.com", "DEEPSEEK_API_KEY"))
            api_key = os.environ.get(env_key, "")
            if not api_key:
                raise RuntimeError(f"环境变量 {env_key} 未设置，无法初始化模型 {self.model}")
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=httpx.Client(
                    trust_env=False,
                    verify=True,
                    timeout=httpx.Timeout(60.0, connect=15.0),
                    limits=httpx.Limits(max_keepalive_connections=3, max_connections=50),
                ),
            )

    @property
    def supports_vision(self) -> bool:
        return self.model in VISION_MODELS

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    def __enter__(self) -> "MathAgent":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    @staticmethod
    def _msg_len(m) -> int:
        c = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        return len(c) if isinstance(c, str) else 4000  # multimodal messages estimated at 4000

    @staticmethod
    def _truncate_msg(m: dict) -> dict:
        c = m.get("content")
        if isinstance(c, str) and len(c) > _MAX_MSG_CHARS:
            m = {**m, "content": c[:_MAX_MSG_CHARS] + "\n… (内容过长已截断) "}
        return m

    @staticmethod
    def _trim_history(history: list) -> list:
        """Keep last _MAX_HISTORY_TURNS turns (each = user+assistant) to avoid context overflow."""
        turns = []
        buf = []
        for msg in reversed(history):
            buf.insert(0, msg)
            if msg.get("role") == "user":
                turns.insert(0, buf)
                buf = []
                if len(turns) >= _MAX_HISTORY_TURNS:
                    break
        return [m for turn in turns for m in turn]

    @staticmethod
    def _compress_history(history: list) -> list:
        """长对话压缩：保留最近轮次原文，更早的轮次摘要成一条 system 消息。"""
        recent = MathAgent._trim_history(history)
        # Apply per-message truncation first
        recent = [MathAgent._truncate_msg(m) for m in recent]
        # Then enforce total token budget by dropping oldest turns
        while len(recent) > 2 and sum(map(MathAgent._msg_len, recent)) > _CTX_BUDGET_CHARS:
            recent.pop(0)
        dropped = history[: len(history) - len(recent)]
        if not dropped:
            return recent
        lines = []
        for m in dropped:
            content = m.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            prefix = "用户" if m.get("role") == "user" else "助教"
            snippet = content.strip().replace("\n", " ")[:120]
            lines.append(f"{prefix}：{snippet}")
        if not lines:
            return recent
        summary = "（以下是早前对话的摘要，供参考，不必逐条回应）\n" + "\n".join(lines[-40:])
        return [{"role": "system", "content": summary[:2000]}] + recent

    def _create_with_retry(self, *, tools, messages, max_tokens, extra, max_retries: int = 3):
        """带指数退避的 API 调用封装。返回 (response, tools_ok)。"""
        tools_ok = tools is not None
        for attempt in range(max_retries + 1):
            try:
                kwargs = dict(model=self.model, messages=messages,
                              max_tokens=max_tokens, extra_body=extra)
                if tools_ok:
                    kwargs["tools"] = tools
                return self.client.chat.completions.create(**kwargs), tools_ok
            except BadRequestError as e:
                msg = str(e).lower()
                # Only downgrade on tool-related 400; context-limit 400 should propagate
                if tools_ok and ("tool" in msg or "function" in msg):
                    tools_ok = False
                    continue
                raise
            except (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError) as e:
                if attempt >= max_retries:
                    raise
                wait = 2 ** attempt  # 1s, 2s, 4s
                _log.warning("API %s, %ds 后重试 (%d/%d)", type(e).__name__, wait, attempt + 1, max_retries)
                time.sleep(wait)

    def solve(
        self,
        problem: str,
        history: Optional[list] = None,
        on_tool_call: Optional[Callable] = None,
        image_bytes: Optional[bytes] = None,
    ) -> Union[str, Iterator]:
        """运行完整的 agentic loop，支持多轮对话历史。

        on_tool_call(name, args, result): 每次工具调用后回调，result=None 表示调用前。
        返回值：普通模式返回 str；vision/guide 模式返回流式响应对象。
        """
        system = _GUIDE_SYSTEM if self.guide_mode else _SYSTEM
        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(self._compress_history(history))

        # vision mode: compress image (reduce tokens) + single direct call
        if image_bytes:
            if not self.supports_vision:
                return "⚠️ 当前模型不支持图片识别，请使用拍题功能或切换到视觉模型。"
            image_bytes = compress_image(image_bytes, max_size=768, quality=80)
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
        extra = {}

        # explain mode: only calculator tool, no draw_mindmap/plot_function
        _EXPLAIN_TOOLS = [t for t in TOOL_DEFINITIONS if t["function"]["name"] == "calculator"]
        _tools_supported = True

        # accumulate text from tool-calling rounds to avoid loss
        _accumulated: list[str] = []

        for iteration in range(self.max_iterations):
            # Guard against context bloat accumulated during the loop
            if sum(map(self._msg_len, messages)) > _CTX_BUDGET_CHARS:
                for m in messages:
                    if isinstance(m, dict) and m.get("role") == "tool" and len(m.get("content", "")) > 500:
                        m["content"] = m["content"][:500] + "… (已截断) "

            _active_tools = (_EXPLAIN_TOOLS if is_explain else TOOL_DEFINITIONS) if _tools_supported else None
            response, _tools_supported = self._create_with_retry(
                tools=_active_tools,
                messages=messages,
                max_tokens=8192,
                extra=extra,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "length":
                _log.warning("response truncated at max_tokens (iteration %d)", iteration)

            # Use msg.tool_calls as the authoritative signal; finish_reason is unreliable on Ollama
            if not msg.tool_calls:
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
                    try:
                        args, _ = json.JSONDecoder().raw_decode(tc.function.arguments.strip())
                    except Exception:
                        args = {}

                _log.debug("tool call: %s args=%s", name, args)

                try:
                    if on_tool_call:
                        on_tool_call(name, args, None)
                except Exception:
                    pass

                try:
                    result = execute_tool(name, args)
                except Exception as exc:
                    _log.warning("tool %s failed: %s (args=%s)", name, exc, args)
                    result = f"[工具执行出错: {type(exc).__name__}: {exc}。请检查参数格式后重试，或改用其他方法]"

                _log.debug("tool result: %s", str(result)[:120])

                try:
                    if on_tool_call:
                        on_tool_call(name, args, result)
                except Exception:
                    pass

                # Truncate oversized tool results to prevent context explosion
                if len(result) > _MAX_TOOL_RESULT_CHARS:
                    result = (result[:_MAX_TOOL_RESULT_CHARS]
                              + f"\n… (结果过长，已截断，原始长度 {len(result)} 字符。"
                              "如需完整结果请缩小计算范围) ")

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      result,
                })

        # iteration limit: ask model to summarize based on accumulated results
        messages.append({"role": "user", "content": "请根据上面的计算结果，直接给出最终答案，不要再调用工具。"})
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=2048,
            )
            return resp.choices[0].message.content or "（无输出）"
        except Exception:
            _log.exception("iteration limit fallback failed")
            return "⚠️ 解题超时，请尝试把题目拆分成更小的步骤发送。"

    def solve_stream(
        self,
        problem: str,
        history: Optional[list] = None,
        on_tool_call: Optional[Callable] = None,
        image_bytes: Optional[bytes] = None,
    ) -> Iterator:
        """Run the full agentic loop, returning an iterable stream object."""
        try:
            result = self.solve(problem, history=history, on_tool_call=on_tool_call, image_bytes=image_bytes)
        except Exception as exc:
            _log.exception("solve failed")
            return _fake_stream(f"⚠️ 解题出错：{exc}")
        if isinstance(result, str):
            return _fake_stream(result)
        return result


def _fake_stream(text: str, chunk_size: int = 2, max_total_delay: float = 30.0) -> Iterator:
    """Yield text in fixed-size chunks with delay to produce visible streaming effect."""
    class _Delta:
        def __init__(self, c): self.content = c
    class _Choice:
        def __init__(self, c): self.delta = _Delta(c)
    class _Chunk:
        def __init__(self, c): self.choices = [_Choice(c)]

    total_chunks = max(1, len(text) // chunk_size)
    delay = min(0.025, max_total_delay / total_chunks)

    for i in range(0, len(text), chunk_size):
        yield _Chunk(text[i:i + chunk_size])
        time.sleep(delay)
