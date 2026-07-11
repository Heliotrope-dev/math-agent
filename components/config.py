import os
import streamlit as st

# ── SiliconFlow ───────────────────────────────────────────────────────────────
SILICONFLOW_BASE      = "https://api.siliconflow.cn"
SILICONFLOW_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"
ASR_TIMEOUT           = 30
OCR_MODEL             = "Qwen/Qwen3-VL-30B-A3B-Instruct"

# ── 默认模型 ──────────────────────────────────────────────────────────────────
# deepseek-chat/deepseek-reasoner 这两个旧模型名 2026-07-24 起停用（DeepSeek
# 官方迁移到 deepseek-v4-flash/deepseek-v4-pro）。deepseek-chat 对应
# deepseek-v4-flash 的"不思考"模式，行为等价，先原样切换过去避免到期断供；
# 要不要换成 v4-pro 的思考模式（数学准确率更高但工具调用协议不同，需要
# 额外处理 reasoning_content 传递）是后续单独评估的事，不在这次改动里。
DEFAULT_MODEL = "deepseek-v4-flash"

# ── 管理员 ────────────────────────────────────────────────────────────────────
ADMIN_EMAIL = "a13989358483@gmail.com"


def get_secret(key: str) -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")
