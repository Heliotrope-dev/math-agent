import os
import streamlit as st

# ── SiliconFlow ───────────────────────────────────────────────────────────────
SILICONFLOW_BASE      = "https://api.siliconflow.cn"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"
ASR_TIMEOUT           = 30
OCR_MODEL             = "Qwen/Qwen3-VL-30B-A3B-Instruct"

# ── 默认模型 ──────────────────────────────────────────────────────────────────
# 2026-08-26从DeepSeek切到千问——跟agent.py CLOUD_PROVIDERS同一次改动，
# 原因和对比数据见那边的注释，这里不重复。这个DEFAULT_MODEL单独给
# rag_engine.py（知识库问答）和_math_page.py的_summarize_wrongbook_entry
# （错题本摘要）用，这两处不走agent.py的CLOUD_PROVIDERS注册表，是各自
# 独立直连API的调用点，要跟着一起切、不能漏改。
DEFAULT_MODEL = "qwen3.7-flash"


def get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")
