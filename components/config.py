import os
import streamlit as st

# ── SiliconFlow ───────────────────────────────────────────────────────────────
SILICONFLOW_BASE      = "https://api.siliconflow.cn"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"
ASR_TIMEOUT           = 30
OCR_MODEL             = "Qwen/Qwen3-VL-30B-A3B-Instruct"

# ── 默认模型 ──────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-chat"

# ── 管理员 ────────────────────────────────────────────────────────────────────
ADMIN_EMAIL = "a13989358483@gmail.com"


def get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")
