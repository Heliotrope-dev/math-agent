import os
import streamlit as st
from openai import OpenAI

# ── SiliconFlow ───────────────────────────────────────────────────────────────
# 2026-09-14起只剩向量嵌入(BAAI/bge-m3)还在用SiliconFlow：文字/拍题/语音/
# 通用OCR全部切到Gemini之后，SILICONFLOW_API_KEY这把key现在只被
# rag_engine.py的embed_texts()用到。嵌入模型没有一起切——现有chroma_db
# 里的向量是bge-m3算出来的，换嵌入模型意味着要把所有已入库文档重新嵌入
# 一遍，是数据迁移，不是简单换个key，先留着没动。
SILICONFLOW_BASE = "https://api.siliconflow.cn"

# ── 默认模型 ──────────────────────────────────────────────────────────────────
# 2026-09-14从千问切到Gemini：跟finance-agent/OpenClaw统一成同一条
# 免费档→付费档故障转移链，避免三个项目各管一套供应商key。这个
# DEFAULT_MODEL单独给rag_engine.py（知识库问答）和_math_page.py的
# _summarize_wrongbook_entry（错题本摘要）用，agent.py走的是自己的
# CLOUD_PROVIDERS注册表（同样已经改成默认Gemini），三处要一起切、
# 不能漏改。
GEMINI_BASE   = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


def get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")


def _is_gemini_quota_error(exc: Exception) -> bool:
    """免费档打满典型返回 429/RESOURCE_EXHAUSTED；额度/余额类错误才转移，
    参数错/鉴权错换哪把key都一样，不转移（会掩盖真正的配置问题）。"""
    txt = f"{type(exc).__name__} {exc}".lower()
    return any(k in txt for k in (
        "429", "resource_exhausted", "quota", "rate limit", "ratelimit",
        "insufficient_quota", "balance is insufficient", "402",
    ))


class _FailoverCompletions:
    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    def create(self, **kwargs):
        if self._primary is None:
            return self._fallback.chat.completions.create(**kwargs)
        try:
            return self._primary.chat.completions.create(**kwargs)
        except Exception as e:
            if self._fallback is not None and _is_gemini_quota_error(e):
                return self._fallback.chat.completions.create(**kwargs)
            raise


class _FailoverChat:
    def __init__(self, primary, fallback):
        self.completions = _FailoverCompletions(primary, fallback)


class GeminiFailoverClient:
    """Gemini 免费档→付费档故障转移。对外接口跟 openai.OpenAI 保持一致
    （.chat.completions.create() / .close()），调用方不用改代码，也不支持
    流式（跟 finance-agent 的 chat_with_failover 一样，流式场景各自处理）。

    两把key的关系：GEMINI_FREE_API_KEY（免费项目，太平洋时间午夜重置额度）
    打头，GEMINI_API_KEY（付费项目，充值余额）兜底。只配一把也能用，行为
    退化成单一供应商。两把都没配才报错。
    """

    def __init__(self, timeout: float = 60.0, max_retries: int = 2):
        free_key = get_secret("GEMINI_FREE_API_KEY")
        paid_key = get_secret("GEMINI_API_KEY")
        if not free_key and not paid_key:
            raise RuntimeError("未配置 GEMINI_FREE_API_KEY / GEMINI_API_KEY。")
        free_c = (OpenAI(api_key=free_key, base_url=GEMINI_BASE, max_retries=max_retries, timeout=timeout)
                  if free_key else None)
        paid_c = (OpenAI(api_key=paid_key, base_url=GEMINI_BASE, max_retries=max_retries, timeout=timeout)
                  if paid_key else None)
        self._clients = [c for c in (free_c, paid_c) if c is not None]
        fallback = self._clients[1] if len(self._clients) > 1 else None
        self.chat = _FailoverChat(self._clients[0], fallback)

    def close(self) -> None:
        for c in self._clients:
            try:
                c.close()
            except Exception:
                pass


def build_gemini_failover_client(timeout: float = 60.0, max_retries: int = 2) -> GeminiFailoverClient:
    return GeminiFailoverClient(timeout=timeout, max_retries=max_retries)
