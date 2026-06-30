"""
app.py — Math Solver Web UI

Launch:
  streamlit run app.py
  USE_LOCAL=1 streamlit run app.py
"""

import os, sys, base64, requests, re, time, random, hashlib, json, secrets as _secrets
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import tempfile

from PIL import Image
import streamlit as st

for _k in ("GEMINI_API_KEY", "DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY", "OLLAMA_BASE_URL"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from agent import MathAgent, LOCAL_MODELS, DEFAULT_LOCAL_MODEL, CLOUD_PROVIDERS

# ── Supabase REST（直接用 requests，无需 supabase 包）────────────────────────
_SB_URL = "https://jqfvgpeyzghnuznjjwio.supabase.co/rest/v1"
_SB_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxZnZncGV5emdobnV6bmpqd2lvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI4MDUxNjUsImV4cCI6MjA5ODM4MTE2NX0"
    ".8DcpQHEsOsjlwzBdYWX_3PaIcFlYgpm_YzbKpFBapqQ"
)
_SB_HDR = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Content-Type": "application/json",
}

def _sb_get(table: str, params: dict) -> list:
    try:
        r = requests.get(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []

def _sb_post(table: str, data: dict | list):
    try:
        requests.post(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, timeout=8)
    except Exception:
        pass

def _sb_delete(table: str, params: dict):
    try:
        requests.delete(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
    except Exception:
        pass

# ── 用户管理（登录注册 + 7天免登录）──────────────────────────────────────────
_TOKEN_DAYS = 7

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _user_exists(email: str) -> bool:
    return len(_sb_get("users", {"email": f"eq.{email}", "select": "email"})) > 0

def _check_user(email: str, pw_hash: str) -> bool:
    return len(_sb_get("users", {
        "email": f"eq.{email}", "password_hash": f"eq.{pw_hash}", "select": "email"
    })) > 0

def _register_user(email: str, pw_hash: str):
    _sb_post("users", {"email": email, "password_hash": pw_hash})

def _create_token(email: str) -> str:
    token = _secrets.token_urlsafe(32)
    now = datetime.now()
    exp = (now + timedelta(days=_TOKEN_DAYS)).isoformat()
    _sb_delete("sessions", {"email": f"eq.{email}", "expires_at": f"lt.{now.isoformat()}"})
    _sb_post("sessions", {"token": token, "email": email, "expires_at": exp})
    return token

def _validate_token(token: str):
    rows = _sb_get("sessions", {
        "token": f"eq.{token}", "expires_at": f"gt.{datetime.now().isoformat()}", "select": "email"
    })
    return rows[0]["email"] if rows else None

def _invalidate_token(token: str):
    _sb_delete("sessions", {"token": f"eq.{token}"})

# ── 错题本持久化（Supabase REST）─────────────────────────────────────────────
def _load_wrong_book(email: str) -> list:
    if not email:
        return []
    return _sb_get("wrong_book", {"email": f"eq.{email}", "select": "question,saved_at", "order": "id"})

def _save_wrong_book(email: str, wb: list):
    if not email:
        return
    _sb_delete("wrong_book", {"email": f"eq.{email}"})
    if wb:
        _sb_post("wrong_book", [
            {"email": email, "question": item["question"], "saved_at": item.get("saved_at", "")}
            for item in wb
        ])

def _show_login_page():
    st.markdown("""
    <div class="login-logo">
        <div class="login-logo-icon">🧮</div>
        <div class="login-logo-title">Math Agent</div>
        <div class="login-logo-sub">AI 数学助教 · 登录后开始使用</div>
    </div>
    """, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        tab_l, tab_r = st.tabs(["登录", "注册"])
        with tab_l:
            _em = st.text_input("邮箱", key="li_email", placeholder="your@email.com")
            _pw = st.text_input("密码", type="password", key="li_pw")
            if st.button("登录", type="primary", use_container_width=True, key="do_login"):
                if _check_user(_em, _hash_pw(_pw)):
                    _tok = _create_token(_em)
                    st.query_params["_auth"] = _tok
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = _em
                    st.session_state["_token"] = _tok
                    st.rerun()
                else:
                    st.error("邮箱或密码不正确")
        with tab_r:
            _rem = st.text_input("邮箱", key="reg_email", placeholder="your@email.com")
            _rpw = st.text_input("密码（至少6位）", type="password", key="reg_pw")
            _rpw2 = st.text_input("确认密码", type="password", key="reg_pw2")
            if st.button("注册账号", type="primary", use_container_width=True, key="do_reg"):
                if not _rem or "@" not in _rem:
                    st.error("请输入有效邮箱")
                elif len(_rpw) < 6:
                    st.error("密码至少6位")
                elif _rpw != _rpw2:
                    st.error("两次密码不一致")
                elif _user_exists(_rem):
                    st.error("该邮箱已注册")
                else:
                    try:
                        _register_user(_rem, _hash_pw(_rpw))
                        st.success("注册成功，请切换到登录标签页")
                    except Exception as _e:
                        st.error(f"注册失败：{_e}")

st.set_page_config(page_title="Math Solver", page_icon="🧮", layout="wide")

# ── URL 参数持久化（7 天免登录）──────────────────────────────────────────────
# st.query_params 存储在 URL 中，刷新后完整保留，无需 JS cookie，100% 可靠
_stored_token = st.query_params.get("_auth", "") or ""
if _stored_token and not st.session_state.get("logged_in"):
    _auto_email = _validate_token(_stored_token)
    if _auto_email:
        st.session_state["logged_in"] = True
        st.session_state["user_email"] = _auto_email
        st.session_state["_token"] = _stored_token
    else:
        try:
            del st.query_params["_auth"]
        except Exception:
            pass

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ══ 全局背景：微信暖米白 ══ */
html, body { background: #EDE5DC !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"],
footer { background: #EDE5DC !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4 { color: #1a1a1a !important; }
#MainMenu, header { visibility: hidden; }
[data-testid="block-container"] { padding-bottom: 180px !important; }

/* ── 侧边栏 ── */
[data-testid="stSidebar"] {
    background: #F0EBE5 !important;
    border-right: 1px solid #D5CEC8 !important;
}
[data-testid="stSidebar"] * { color: #2a2a2a !important; }
[data-testid="stSidebar"] .stButton button {
    background: #E8E2DC !important;
    border: 1px solid #CCC6C0 !important;
    color: #444 !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: #DEDAD4 !important; color: #111 !important;
}

/* ── 顶部标题 ── */
.app-header {
    display: flex; align-items: center; gap: 10px;
    padding: 0.5rem 0 1rem; border-bottom: 1px solid #D4CEC8;
}
.app-header-title { font-size: 1rem; font-weight: 600; color: #555 !important; }

/* ── 欢迎页 ── */
.welcome-wrap { text-align: center; padding: 2.5rem 0 1.5rem; }
.welcome-title { font-size: 1.8rem; font-weight: 600; color: #1a1a1a !important; margin-bottom: 0.5rem; }
.welcome-sub { font-size: 0.88rem; color: #888 !important; margin-bottom: 2rem; }

/* ── 示例卡片 ── */
[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: #FFFFFF !important;
    border: 1px solid #D5CEC8 !important;
    border-radius: 12px !important;
    color: #333 !important;
    font-size: 0.85rem !important;
    padding: 12px 16px !important;
    text-align: left !important;
    line-height: 1.45 !important;
    min-height: 56px !important;
    height: auto !important;
    white-space: normal !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    background: #F5F0EB !important;
    border-color: #A8A0A0 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 8px rgba(0,0,0,0.1) !important;
}

/* ── 换一批 ── */
.refresh-btn button {
    background: transparent !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 20px !important;
    color: #888 !important; font-size: 0.82rem !important;
}
.refresh-btn button:hover { border-color: #999 !important; color: #444 !important; }

/* ── 微信气泡：用户（右）── */
.bubble-user {
    background: #95EC69;
    color: #111;
    border-radius: 18px 4px 18px 18px;
    padding: 10px 14px;
    word-break: break-word;
    line-height: 1.6;
    font-size: 0.95rem;
    display: inline-block;
    max-width: 100%;
}
/* ── 微信气泡：AI（左）── */
.bubble-asst-wrap {
    background: #FFFFFF;
    border-radius: 4px 18px 18px 18px;
    padding: 10px 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    word-break: break-word;
    line-height: 1.6;
    font-size: 0.95rem;
}
.bubble-asst-wrap p, .bubble-asst-wrap li { color: #1a1a1a !important; }

.msg-row-user {
    display: flex; justify-content: flex-end; align-items: flex-end;
    gap: 8px; margin: 8px 0;
}
.msg-row-asst {
    display: flex; justify-content: flex-start; align-items: flex-end;
    gap: 8px; margin: 8px 0;
}
/* 头像圆角方块（微信风格）*/
.av {
    width: 36px; height: 36px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
}
.av-ai   { background: #5CBE6E; }
.av-user { background: #7BC47B; }

/* ── 引导模式开关条 ── */
.guide-bar { display: flex; align-items: center; gap: 8px; padding: 2px 0 4px; }
.guide-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: #E8E2DC; border: 1px solid #C8C2BC; border-radius: 20px;
    padding: 4px 12px; font-size: 0.82rem; color: #555;
    cursor: pointer; user-select: none; transition: all 0.15s;
}
.guide-chip.on { background: #2aae67; border-color: #2aae67; color: #fff; }

/* ── 加号面板 ── */
.plus-panel {
    background: #F5F0EB; border: 1px solid #D4CEC8;
    border-radius: 16px; padding: 16px 12px; margin: 8px 0;
}
.plus-panel .stButton button {
    background: #FFFFFF !important; border: 1px solid #D0CAC4 !important;
    border-radius: 12px !important; padding: 14px 6px !important;
    height: 76px !important; font-size: 0.82rem !important; color: #444 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
.plus-panel .stButton button:hover {
    background: #EDE5DC !important; border-color: #AAA !important; color: #111 !important;
}

/* ── 工具栏图标按钮 ── */
.toolbar-btn button {
    background: transparent !important; border: none !important;
    font-size: 1.4rem !important; padding: 6px !important;
    border-radius: 50% !important; color: #666 !important;
    height: 44px !important; width: 44px !important;
}
.toolbar-btn button:hover { background: #D8D0C8 !important; color: #222 !important; }

/* ── 输入框 ── */
[data-testid="stChatInputContainer"] {
    background: #EDE5DC !important;
    border-top: 1px solid #D4CEC8 !important;
    padding: 8px 16px 14px !important;
}
[data-testid="stChatInputTextArea"] {
    background: #FFFFFF !important; border: 1px solid #C8C0B8 !important;
    border-radius: 24px !important; color: #1a1a1a !important;
    font-size: 0.95rem !important; padding: 10px 16px !important;
}
[data-testid="stChatInputTextArea"]:focus {
    border-color: #2aae67 !important;
    box-shadow: 0 0 0 2px rgba(42,174,103,0.15) !important;
}
[data-testid="stChatInputSubmitButton"] button {
    background: #2aae67 !important; border-radius: 50% !important;
}

/* ── 知识点 pills（全覆盖，优先级最高）── */
[data-testid="stPills"] { margin-top: 8px !important; }
div[data-testid="stPills"] > div > label > div,
div[data-testid="stPills"] button,
div[data-testid="stPills"] [role="radio"],
div[data-testid="stPills"] [role="button"] {
    background-color: #F0EBE5 !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 20px !important;
    color: #444444 !important;
    font-size: 0.78rem !important;
    padding: 3px 12px !important;
}
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-checked="true"],
div[data-testid="stPills"] button[aria-selected="true"],
div[data-testid="stPills"] [aria-checked="true"],
div[data-testid="stPills"] [aria-selected="true"] {
    background-color: #2aae67 !important;
    border-color: #2aae67 !important;
    color: #ffffff !important;
}
div[data-testid="stPills"] p,
div[data-testid="stPills"] span { color: inherit !important; background: transparent !important; }

/* ── 通用按钮 ── */
.stButton button { border-radius: 8px !important; font-size: 0.84rem !important; }
.stButton button[kind="primary"] {
    background: #2aae67 !important; border: none !important; color: #fff !important;
}
.stButton button[kind="primary"]:hover { background: #25a05e !important; }

/* ── 轮次标签 ── */
.turn-badge {
    display: inline-block; background: #E8E2DC; border: 1px solid #C8C0B8;
    color: #888; padding: 1px 8px; border-radius: 6px; font-size: 0.7rem; margin-bottom: 4px;
}

/* ── expander ── */
[data-testid="stExpander"] {
    border: 1px solid #D4CEC8 !important; border-radius: 10px !important;
    background: #F5F0EB !important;
}

/* ── Status ── */
[data-testid="stStatusWidget"] {
    background: #F5F0EB !important; border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
}

/* ── 代码块 ── */
pre, code {
    background: #F0EBE5 !important; border: 1px solid #D4CEC8 !important;
    border-radius: 8px !important; font-size: 0.82rem !important; color: #333 !important;
}

hr { border-color: #D4CEC8 !important; }

/* ── 麦克风 ── */
[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div {
    background: #F5F0EB !important; border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
}
/* 录音 / 停止 按钮放大 */
[data-testid="stAudioInput"] button {
    background: transparent !important; color: #555 !important;
    width: 72px !important; height: 72px !important;
    min-width: 72px !important; border-radius: 50% !important;
}
[data-testid="stAudioInput"] button svg {
    width: 36px !important; height: 36px !important;
}

/* ── 语音识别文本框（样式与聊天输入框一致）── */
[data-testid="stTextArea"] textarea {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 16px !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    padding: 10px 16px !important;
    resize: none !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #2aae67 !important;
    box-shadow: 0 0 0 2px rgba(42,174,103,0.15) !important;
}

/* ══ 文件上传：白色圆角按钮，隐藏虚线框和小字说明 ══ */
[data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploadDropzone"] {
    background: transparent !important;
    border: none !important;
    padding: 4px 0 !important;
}
/* 隐藏 "Drag and drop" / "200MB per file" 小字 */
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploadDropzone"] small {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] > div > span,
[data-testid="stFileUploadDropzone"] > div > span {
    display: none !important;
}
/* 上传按钮：全宽白色圆角 */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 14px !important;
    color: #333 !important;
    width: 100% !important;
    padding: 14px 20px !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    justify-content: center !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover {
    background: #F5F0EB !important;
    border-color: #888 !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: #FFFFFF !important;
    border: 1px solid #C8C0B8 !important;
    border-radius: 10px !important;
    color: #1a1a1a !important;
}
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul { background: #FFFFFF !important; }
[data-baseweb="menu"] li { color: #1a1a1a !important; }
[data-baseweb="menu"] li:hover { background: #F0EBE5 !important; }

/* ── Checkbox / Toggle ── */
[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: #1a1a1a !important; }

/* ── 底部完全覆盖（包括 stBottom sticky 区域）── */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div {
    background: #EDE5DC !important;
}

/* ── 工具栏容器透明 ── */
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }
[data-testid="element-container"] { background: transparent !important; }

/* ── 工具栏里的 selectbox 紧凑 ── */
.toolbar-model [data-testid="stSelectbox"] > div > div {
    border: 1px solid #C8C0B8 !important;
    background: rgba(255,255,255,0.7) !important;
    font-size: 0.82rem !important;
    color: #333 !important;
    padding: 4px 10px !important;
    min-height: 36px !important;
    border-radius: 20px !important;
}

/* ── 欢迎问候语 ── */
.greeting-wrap {
    text-align: center;
    padding: 4rem 0 2rem;
}
.greeting-main {
    font-size: 2rem;
    font-weight: 600;
    color: #1a1a1a !important;
    margin-bottom: 0.4rem;
}
.greeting-sub {
    font-size: 0.9rem;
    color: #999 !important;
}

/* ── 侧边栏历史记录 ── */
[data-testid="stSidebar"] .stButton button {
    text-align: left !important;
    font-size: 0.8rem !important;
    padding: 6px 10px !important;
    height: auto !important;
    min-height: 32px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: block !important;
}

/* ── 功能介绍卡片 ── */
.feature-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin: 20px 0 12px;
}
.feature-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 14px 12px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    border: 1px solid #EAE4DE;
}
.feature-icon { font-size: 1.5rem; margin-bottom: 6px; }
.feature-title { font-size: 0.88rem; font-weight: 600; color: #1a1a1a !important; margin-bottom: 4px; }
.feature-desc { font-size: 0.75rem; color: #888 !important; line-height: 1.4; }

/* ── 汉堡菜单（仅手机显示）── */
.hamburger-wrap button {
    display: none !important;
}
@media (max-width: 768px) {
    .hamburger-wrap button {
        display: flex !important;
        background: transparent !important;
        border: none !important;
        font-size: 1.3rem !important;
        color: #555 !important;
        padding: 4px 6px !important;
        border-radius: 6px !important;
        align-items: center !important;
        justify-content: center !important;
        height: 36px !important;
        width: 36px !important;
    }
    .hamburger-wrap button:hover {
        background: #D8D0C8 !important;
    }
}

/* ── 存入错题本 ── */
button[kind="secondary"][data-testid*="wb_add"] {
    font-size: 0.75rem !important;
    color: #888 !important;
    border-color: #DDD !important;
    padding: 2px 10px !important;
    height: auto !important;
    min-height: 28px !important;
    border-radius: 14px !important;
    background: transparent !important;
}

/* ── 登录页 ── */
.login-logo {
    text-align: center;
    padding: 60px 0 24px;
}
.login-logo-icon { font-size: 3rem; }
.login-logo-title { font-size: 1.5rem; font-weight: 600; color: #1a1a1a !important; margin: 8px 0 4px; }
.login-logo-sub { font-size: 0.85rem; color: #888 !important; }

/* ══ 手机端响应式 ══ */
@media (max-width: 768px) {
    /* 侧边栏折叠 */
    [data-testid="stSidebar"] { display: none !important; }
    /* 强制所有列横排，不折行 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 4px !important;
    }
    [data-testid="stColumn"] {
        min-width: 0 !important;
        flex-shrink: 1 !important;
        overflow: hidden !important;
    }
    /* 气泡宽度自适应 */
    .bubble-user { max-width: 80vw !important; font-size: 0.9rem !important; }
    .bubble-asst-wrap { font-size: 0.9rem !important; }
    /* 欢迎语 */
    .greeting-main { font-size: 1.4rem !important; }
    /* 工具栏在小屏更紧凑 */
    .toolbar-model [data-testid="stSelectbox"] > div > div {
        font-size: 0.68rem !important; padding: 2px 6px !important; min-height: 32px !important;
    }
    .toolbar-btn button {
        width: 36px !important; height: 36px !important; font-size: 1.1rem !important;
    }
    /* 头像缩小 */
    .av { width: 28px !important; height: 28px !important; font-size: 0.9rem !important; }
    /* 头部 */
    .app-header-title { font-size: 0.9rem !important; }
    /* 输入框 */
    [data-testid="stChatInputTextArea"] { font-size: 0.9rem !important; }
    /* 功能卡片 */
    .feature-card { padding: 10px 8px; }
    .feature-title { font-size: 0.82rem !important; }
    .feature-desc { font-size: 0.7rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ── 登录检查（未登录则显示登录页并阻止后续渲染）─────────────────────────────
if not st.session_state.get("logged_in"):
    _show_login_page()
    st.stop()

# ── 配置 ──────────────────────────────────────────────────────────────────────
_USE_LOCAL = os.environ.get("USE_LOCAL", "0") == "1"

def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

# ── 示例题目池（30+ 题，每次随机抽 6 道）────────────────────────────────────
_ALL_EXAMPLES = [
    "解方程 2x² + 5x − 3 = 0",
    "解方程组：x + y = 5，2x − y = 1",
    "化简 (x² − 4) / (x + 2)",
    "展开 (x + 2)⁴，保留完整系数",
    "解不等式 |2x − 3| < 5",
    "求导：f(x) = x³ · sin(x)",
    "求导：g(x) = ln(x² + 1)",
    "求 y = eˣ · cos(x) 的导数",
    "求 f(x) = arctan(2x) 的导数",
    "求 f(x) = xˣ 的导数",
    "计算定积分 ∫₀¹ x² dx",
    "计算不定积分 ∫ x · eˣ dx",
    "计算 ∫ sin²(x) dx",
    "计算广义积分 ∫₁^∞ 1/x² dx",
    "分部积分法计算 ∫ x · ln(x) dx",
    "求极限 lim(x→0) sin(x)/x",
    "洛必达法则求 lim(x→0) (eˣ − 1)/x",
    "求 lim(x→∞) (1 + 1/x)ˣ",
    "求 lim(x→0) (1 − cos x) / x²",
    "计算行列式 |1 2; 3 4|",
    "求矩阵 [[2,1],[1,3]] 的特征值",
    "解线性方程组 x + 2y = 3，3x + 4y = 5",
    "求向量 (1,2,3) 和 (4,5,6) 的点积与夹角",
    "等差数列首项 2，公差 3，求第 10 项和前 n 项和",
    "等比数列首项 1，公比 2，求前 8 项和",
    "判断级数 Σ(1/n²) 是否收敛",
    "求 eˣ 在 x=0 处的泰勒展开前 5 项",
    "直角三角形两直角边 3 和 4，求斜边和面积",
    "圆心 (1,2)、半径 5，写出圆的方程",
    "求抛物线 y = x² 在 x=1 处的切线方程",
    "掷两枚骰子，点数之和为 7 的概率",
    "正态分布 N(0,1) 中 P(−1 < X < 1) = ?",
    "二项分布 B(10, 0.3) 的期望和方差",
    "用 Simpson 公式（n=4）估算 ∫₀¹ eˣ dx 的误差",
    "查公式：柯西积分公式",
    "查公式：欧拉公式 eⁱθ",
]

def _get_examples(n=6):
    return random.sample(_ALL_EXAMPLES, min(n, len(_ALL_EXAMPLES)))

# ── Agent ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_agent(use_local, model, guide_mode=False):
    return MathAgent(use_local=use_local, model=model, guide_mode=guide_mode)

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def fix_latex(text):
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', r'\n$$\1$$\n', text, flags=re.DOTALL)
    text = re.sub(r'\\\(\s*(.*?)\s*\\\)', r'$\1$', text, flags=re.DOTALL)
    return text

def extract_tags(text):
    match = re.search(r'📚\s*\*{0,2}知识点\*{0,2}\s*[：:](.*?)$', text, re.MULTILINE)
    if not match:
        return text, []
    tags = [t.strip() for t in re.split(r'[·・,，、]+', match.group(1).strip()) if t.strip()]
    return text[:match.start()].rstrip(), tags

def extract_practice(text):
    match = re.search(r'🧪\s*\*{0,2}例题\*{0,2}\s*[：:](.*?)$', text, re.MULTILINE)
    if not match:
        return text, ""
    practice = match.group(1).strip()
    return text[:match.start()].rstrip(), practice

def _compress_image(image_bytes, max_size=800):
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        st.warning(f"图片压缩失败: {e}")
        return image_bytes

def ocr_math_image(image_bytes):
    key = _secret("GEMINI_API_KEY")
    if not key:
        return "（未配置 GEMINI_API_KEY，无法识别图片）"
    try:
        b64 = base64.b64encode(_compress_image(image_bytes)).decode()
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            json={"contents": [{"parts": [
                {"text": "请识别图片中的数学题，只输出题目原文，不要解答"},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]}]},
            timeout=20,
        )
        data = resp.json()
        if "candidates" not in data:
            return f"识别失败：{data.get('error', {}).get('message', str(data))}"
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"识别失败：{e}"


def transcribe_audio(audio_file) -> str:
    """用 Gemini 把录音转成数学题文字（支持中英文）。"""
    key = _secret("GEMINI_API_KEY")
    if not key:
        return ""
    try:
        raw = audio_file.read()
        # 检测 MIME 类型（浏览器一般录 webm 或 wav）
        mime = "audio/webm"
        if raw[:4] == b"RIFF":
            mime = "audio/wav"
        elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
            mime = "audio/mp3"
        b64 = base64.b64encode(raw).decode()
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
            json={"contents": [{"parts": [
                {"text": (
                    "这是一段数学题的语音录音。"
                    "请把语音内容逐字转录成文字，保留数学符号和表达式。"
                    "中文说的用中文输出，英文说的用英文输出，混合则混合输出。"
                    "只输出转录文字，不要解答，不要加任何说明。"
                )},
                {"inline_data": {"mime_type": mime, "data": b64}},
            ]}]},
            timeout=30,
        )
        data = resp.json()
        if "candidates" not in data:
            return ""
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return ""

# ── Session state ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "wrong_book" not in st.session_state:
    # 登录后从磁盘加载，未登录为空
    st.session_state.wrong_book = _load_wrong_book(st.session_state.get("user_email", ""))
if "example_set" not in st.session_state:
    st.session_state.example_set = _get_examples()
if "show_photo" not in st.session_state:
    st.session_state.show_photo = False
if "show_file" not in st.session_state:
    st.session_state.show_file = False
if "guide_mode" not in st.session_state:
    st.session_state.guide_mode = False
if "show_mobile_menu" not in st.session_state:
    st.session_state.show_mobile_menu = False

# ── 侧边栏 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # ── 用户信息 + 退出 ──────────────────────────────────────────────────────
    _uemail = st.session_state.get("user_email", "")
    st.markdown(
        f'<p style="font-size:0.75rem;color:#888;margin:0 0 4px">👤 {_uemail}</p>',
        unsafe_allow_html=True,
    )
    if st.button("退出登录", key="logout_btn", use_container_width=True):
        _tok = st.session_state.pop("_token", None)
        if _tok:
            _invalidate_token(_tok)
        try:
            del st.query_params["_auth"]
        except Exception:
            pass
        st.session_state["logged_in"] = False
        st.session_state.pop("user_email", None)
        st.rerun()
    st.divider()

    # ── 最近问题（最多显示10条，超出自动删最早）────────────────────────────────
    _user_msgs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if _user_msgs:
        st.markdown('<p style="font-size:0.75rem;color:#888;margin:0 0 6px">最近问题</p>',
                    unsafe_allow_html=True)
        for _qi, _q in enumerate(_user_msgs[-10:]):
            _q_short = _q[:28] + "…" if len(_q) > 28 else _q
            if st.button(_q_short, key=f"hist_{_qi}", use_container_width=True):
                st.session_state["prefill"] = _q
                st.rerun()
        st.divider()

    wrong_book = st.session_state.wrong_book
    with st.expander(f"错题本（{len(wrong_book)}）", expanded=False):
        if not wrong_book:
            st.caption("解完题后点「存入错题本」")
        else:
            for wi, wp in enumerate(wrong_book):
                q_preview = wp["question"][:48] + ("…" if len(wp["question"]) > 48 else "")
                st.markdown(f"**{wi+1}.** {q_preview}")
                st.caption(wp.get("saved_at", ""))
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("重做", key=f"wb_redo_{wi}", use_container_width=True):
                        st.session_state["prefill"] = wp["question"]
                        st.rerun()
                with c2:
                    if st.button("删除", key=f"wb_del_{wi}", use_container_width=True):
                        st.session_state.wrong_book.pop(wi)
                        _save_wrong_book(_uemail, st.session_state.wrong_book)
                        st.rerun()

    if st.button("清空对话", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("prefill", None)
        st.rerun()

# ── 主界面顶部（含手机端 ☰ 菜单按钮）────────────────────────────────────────
_hdr_menu_col, _hdr_title_col, _hdr_right_col = st.columns([1, 5, 2])
with _hdr_menu_col:
    st.markdown('<div class="hamburger-wrap">', unsafe_allow_html=True)
    _menu_icon = "✕" if st.session_state.show_mobile_menu else "☰"
    if st.button(_menu_icon, key="mobile_menu_btn"):
        st.session_state.show_mobile_menu = not st.session_state.show_mobile_menu
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
with _hdr_title_col:
    st.markdown(
        '<div class="app-header"><span class="app-header-title">🧮 &nbsp; Math Agent</span></div>',
        unsafe_allow_html=True,
    )
_ADMIN_EMAIL = "a13989358483@gmail.com"
with _hdr_right_col:
    _is_admin = st.session_state.get("user_email", "") == _ADMIN_EMAIL
    if _is_admin:
        use_local = st.checkbox("离线 Ollama", value=_USE_LOCAL, key="top_use_local")
    else:
        use_local = False

# ── 手机端弹出菜单（覆盖主内容区）────────────────────────────────────────────
if st.session_state.show_mobile_menu:
    st.markdown("---")
    _mob_msgs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if _mob_msgs:
        st.markdown('<p style="font-size:0.8rem;font-weight:600;margin-bottom:6px">📋 最近问题</p>',
                    unsafe_allow_html=True)
        for _mi, _mq in enumerate(_mob_msgs[-10:]):
            _ms = _mq[:30] + "…" if len(_mq) > 30 else _mq
            if st.button(_ms, key=f"mob_hist_{_mi}", use_container_width=True):
                st.session_state["prefill"] = _mq
                st.session_state.show_mobile_menu = False
                st.rerun()
        st.markdown("---")
    _mob_wb = st.session_state.wrong_book
    if _mob_wb:
        st.markdown(f'<p style="font-size:0.8rem;font-weight:600;margin-bottom:6px">📌 错题本（{len(_mob_wb)}）</p>',
                    unsafe_allow_html=True)
        for _mwi, _mwp in enumerate(_mob_wb):
            _mwq = _mwp["question"][:30] + "…" if len(_mwp["question"]) > 30 else _mwp["question"]
            if st.button(f"重做：{_mwq}", key=f"mob_wb_{_mwi}", use_container_width=True):
                st.session_state["prefill"] = _mwp["question"]
                st.session_state.show_mobile_menu = False
                st.rerun()
        st.markdown("---")
    if st.button("🗑️ 清空对话", key="mob_clear", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("prefill", None)
        st.session_state.show_mobile_menu = False
        st.rerun()
    if st.button("← 返回对话", key="mob_back", type="primary", use_container_width=True):
        st.session_state.show_mobile_menu = False
        st.rerun()
    st.stop()

# selected_model 从工具栏取（见下方 toolbar），先给默认值
selected_model = st.session_state.get("_sel_model", "deepseek-chat")

# ── 欢迎页（无对话时）────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown(
        '<div class="greeting-wrap">'
        '<div class="greeting-main">你好，有什么数学问题？</div>'
        '<div class="greeting-sub">微积分 &nbsp;·&nbsp; 方程 &nbsp;·&nbsp; 线性代数 &nbsp;·&nbsp; 概率统计 &nbsp;·&nbsp; 拍题上传</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    examples = st.session_state.example_set
    cols = st.columns(2, gap="small")
    for idx, ex in enumerate(examples):
        with cols[idx % 2]:
            if st.button(ex, key=f"ex_{idx}", use_container_width=True):
                st.session_state["_direct_input"] = ex

    _, mid, _ = st.columns([2, 1, 2])
    with mid:
        if st.button("↻ 换一批", key="refresh_ex", use_container_width=True):
            st.session_state.example_set = _get_examples()
            st.rerun()

    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <div class="feature-icon">📐</div>
            <div class="feature-title">精准解题</div>
            <div class="feature-desc">多工具协作，完整推导过程与答案</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📷</div>
            <div class="feature-title">拍题识别</div>
            <div class="feature-desc">拍照或上传图片，AI 识别并解答</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🎙️</div>
            <div class="feature-title">语音提问</div>
            <div class="feature-desc">支持中英文语音识别，说题即解</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🧭</div>
            <div class="feature-title">引导学习</div>
            <div class="feature-desc">苏格拉底式教学，引导自主思考</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── 对话历史（微信气泡：AI 左，用户 右）──────────────────────────────────────
_asst_turn = 0
for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]

    if role == "user":
        # 右侧：空白 + 内容 + 头像
        _, _bubble_col, _av_col = st.columns([2, 5, 1])
        with _bubble_col:
            _img_html = ""
            if msg.get("image_b64"):
                _img_html = (
                    f'<img src="data:image/jpeg;base64,{msg["image_b64"]}" '
                    f'style="max-width:180px;border-radius:8px;margin-bottom:6px;display:block">'
                )
            _safe_txt = msg["content"].replace("<", "&lt;").replace(">", "&gt;")
            st.markdown(
                f'<div class="msg-row-user">'
                f'<div class="bubble-user">{_img_html}{_safe_txt}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _av_col:
            st.markdown('<div class="av av-user">👤</div>', unsafe_allow_html=True)
    else:
        _asst_turn += 1
        _av_col2, _bubble_col2, _ = st.columns([1, 6, 1])
        with _av_col2:
            st.markdown('<div class="av av-ai">🧮</div>', unsafe_allow_html=True)
        with _bubble_col2:
            st.markdown(f'<span class="turn-badge">第 {_asst_turn} 轮</span>',
                        unsafe_allow_html=True)
            with st.container(border=False):
                st.markdown(
                    '<div class="bubble-asst-wrap">',
                    unsafe_allow_html=True,
                )
                st.markdown(fix_latex(msg["content"]))
                st.markdown('</div>', unsafe_allow_html=True)
                if msg.get("tags"):
                    tag_key = f"ktag_{i}"
                    sel = st.pills("知识点", msg["tags"], key=tag_key,
                                   label_visibility="collapsed")
                    if sel:
                        st.session_state.pop(tag_key, None)
                        st.session_state["prefill"] = (
                            f"请详细讲解「{sel}」：定义、推导过程和典型例题"
                        )
                        st.rerun()
                if msg.get("practice"):
                    st.markdown(
                        '<p style="font-size:0.8rem;color:#888;margin:6px 0 2px">🧪 同类练习题</p>',
                        unsafe_allow_html=True,
                    )
                    if st.button(msg["practice"], key=f"practice_{i}", use_container_width=True):
                        st.session_state["_direct_input"] = msg["practice"]
                        st.rerun()
                if msg.get("trace"):
                    with st.expander("工具调用详情", expanded=False):
                        st.code(msg["trace"], language="text")
                # ── 存入错题本按钮 ──
                _prev_q = next((m["content"] for m in reversed(st.session_state.messages[:i])
                                if m["role"] == "user"), "")
                if _prev_q and not any(w["question"] == _prev_q for w in st.session_state.wrong_book):
                    if st.button("📌 存入错题本", key=f"wb_add_{i}", use_container_width=False):
                        st.session_state.wrong_book.append({
                            "question": _prev_q,
                            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        })
                        _save_wrong_book(st.session_state.get("user_email",""), st.session_state.wrong_book)
                        st.rerun()

# ── 新消息占位容器（必须在工具栏之前声明，确保新消息渲染在工具栏上方）────────
_new_turn = st.container()

# ── 举一反三触发 ──────────────────────────────────────────────────────────────
_similar_ctx = st.session_state.pop("_similar", None)

_last_user_q = next((m["content"] for m in reversed(st.session_state.messages)
                     if m["role"] == "user"), None)
_last_asst_a = next((m for m in reversed(st.session_state.messages)
                     if m["role"] == "assistant"), None)
_can_act = bool(_last_user_q and _last_asst_a)

# ── 加号面板（4 功能：图片 / 文件 / 举一反三 / 引导模式）────────────────────
if st.session_state.get("show_plus"):
    with st.container():
        st.markdown(
            '<div style="background:#F5F0EB;border:1px solid #D4CEC8;'
            'border-radius:16px;padding:12px 8px;margin:6px 0">',
            unsafe_allow_html=True,
        )
        gc1, gc2, gc3, gc4 = st.columns(4)
        with gc1:
            if st.button("🖼️\n\n图片", key="gp_photo", use_container_width=True):
                st.session_state.show_plus = False
                st.session_state.show_photo = True
                st.rerun()
        with gc2:
            if st.button("📄\n\n文件", key="gp_file", use_container_width=True):
                st.session_state.show_plus = False
                st.session_state.show_file = True
                st.rerun()
        with gc3:
            if st.button("🎯\n\n举一反三", key="gp_sim", use_container_width=True,
                         disabled=not _can_act):
                if _can_act:
                    st.session_state["_similar"] = {
                        "question": _last_user_q,
                        "answer": _last_asst_a["content"][:400],
                    }
                    st.session_state.show_plus = False
                    st.rerun()
        with gc4:
            _gm_active = st.session_state.guide_mode
            _gm_lbl = "🧭\n\n引导✓" if _gm_active else "🧭\n\n引导"
            if st.button(_gm_lbl, key="gp_guide", use_container_width=True):
                st.session_state.guide_mode = not _gm_active
                st.session_state.show_plus = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ── 图片面板：手机点"Browse files"会弹出相机/相册选择 ──────────────────────
if st.session_state.get("show_photo"):
    _pf = st.file_uploader(
        "📷  拍照 / 从相册选取",
        type=["jpg", "jpeg", "png", "webp", "heic"],
        key="photo_inline",
        label_visibility="visible",
    )
    if _pf:
        _pb_ready = _pf.read()
        # 自动存为待发附件，关闭面板，用户在聊天框补说明后发送
        st.session_state["pending_attachment"] = {"type": "image", "bytes": _pb_ready, "name": _pf.name}
        st.session_state.show_photo = False
        st.rerun()

# ── 文件面板：txt/md 内容附加到消息里 ───────────────────────────────────────
if st.session_state.get("show_file"):
    _ff = st.file_uploader("📄 选择文本文件", type=["txt","md"],
                           key="file_inline", label_visibility="visible")
    if _ff:
        _fc = _ff.read().decode("utf-8", errors="replace")
        st.code(_fc[:300] + ("…" if len(_fc) > 300 else ""), language="text")
        # 自动存为待发附件，用户在聊天框补说明后发送
        st.session_state["pending_attachment"] = {"type": "file", "content": _fc, "name": _ff.name}
        st.session_state.show_file = False
        st.rerun()

# ── 麦克风面板（录完立即识别，显示可编辑预览）───────────────────────────────
if st.session_state.get("show_mic"):
    _av = st.audio_input("🎙️ 说出数学题（支持中英文）", key="mic_input",
                         label_visibility="visible")
    if _av:
        with st.spinner("识别中…"):
            _vt = transcribe_audio(_av)
        st.session_state.show_mic = False
        if _vt:
            st.session_state["voice_transcript"] = _vt
        else:
            st.warning("未能识别，请重试或检查 GEMINI_API_KEY")
        st.rerun()

# ── 语音识别完成 → 可编辑预览框（原生 text_input，不依赖 JS）──────────────
if "voice_transcript" in st.session_state and "_vt_widget" not in st.session_state:
    st.session_state["_vt_widget"] = st.session_state.pop("voice_transcript")
elif "voice_transcript" in st.session_state:
    del st.session_state["voice_transcript"]

if "_vt_widget" in st.session_state:
    st.markdown(
        '<p style="font-size:0.82rem;color:#2aae67;margin:4px 0 2px 2px">🎙️ 语音识别完成 · 编辑后点发送</p>',
        unsafe_allow_html=True,
    )
    _vt_c, _vt_btn, _vt_x = st.columns([8, 1, 1])
    with _vt_c:
        st.text_input("", key="_vt_widget", label_visibility="collapsed")
    with _vt_btn:
        if st.button("➤", key="vt_send", type="primary", use_container_width=True):
            _val = st.session_state.get("_vt_widget", "").strip()
            if _val:
                st.session_state["_direct_input"] = _val
                del st.session_state["_vt_widget"]
                st.rerun()
    with _vt_x:
        if st.button("✕", key="vt_cancel", use_container_width=True):
            del st.session_state["_vt_widget"]
            st.rerun()

# ── 待发附件预览条（紧凑横条）────────────────────────────────────────────────
_patt = st.session_state.get("pending_attachment")
if _patt:
    if _patt["type"] == "image":
        _thumb_b64 = base64.b64encode(_compress_image(_patt["bytes"], max_size=80)).decode()
        _icon_html = (
            f'<img src="data:image/jpeg;base64,{_thumb_b64}" '
            f'style="width:44px;height:44px;object-fit:cover;border-radius:8px;flex-shrink:0">'
        )
        _label = _patt.get("name", "图片")
    elif _patt["type"] == "file":
        _icon_html = '<span style="font-size:1.4rem">📄</span>'
        _label = _patt.get("name", "文件")
    else:
        _icon_html = '<span style="font-size:1.4rem">🎙️</span>'
        _label = "语音"

    _pa_col, _px_col = st.columns([10, 1])
    with _pa_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'background:#F5F0EB;border:1px solid #D4CEC8;border-radius:12px;'
            f'padding:8px 12px;margin:4px 0">'
            f'{_icon_html}'
            f'<span style="font-size:0.8rem;color:#555;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap">'
            f'📎 {_label} · 补充说明后发送</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _px_col:
        if st.button("✕", key="cancel_attach"):
            del st.session_state["pending_attachment"]
            st.rerun()

# ── 底部工具栏（Claude 风格：🎙️ · 模型选择 · 引导 · ➕）────────────────────
guide_mode = st.session_state.guide_mode
_tb_mic, _tb_model, _tb_plus = st.columns([1, 8, 1], gap="small")

with _tb_mic:
    st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
    if st.button("✕" if st.session_state.get("show_mic") else "🎙️", key="tb_mic"):
        _on = st.session_state.get("show_mic", False)
        st.session_state.show_mic = not _on
        st.session_state.show_plus = False
        st.session_state.show_photo = False
        st.session_state.show_file = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with _tb_model:
    st.markdown('<div class="toolbar-model">', unsafe_allow_html=True)
    if use_local:
        selected_model = st.selectbox(
            "模型", LOCAL_MODELS, index=LOCAL_MODELS.index(DEFAULT_LOCAL_MODEL),
            label_visibility="collapsed", key="tb_model_local",
        )
    else:
        _copts = list(CLOUD_PROVIDERS.keys())
        _def_idx = _copts.index("deepseek-chat")
        selected_model = st.selectbox(
            "模型", _copts, index=_def_idx,
            label_visibility="collapsed", key="tb_model_cloud",
        )
    st.session_state["_sel_model"] = selected_model
    st.markdown('</div>', unsafe_allow_html=True)

with _tb_plus:
    st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
    if st.button("✕" if st.session_state.get("show_plus") else "➕", key="tb_plus"):
        st.session_state.show_plus = not st.session_state.get("show_plus", False)
        st.session_state.show_mic = False
        st.session_state.show_photo = False
        st.session_state.show_file = False
        st.session_state["_panel_just_toggled"] = True  # 防止误触发发送
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── 文字输入（固定底部）──────────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
_direct_input = st.session_state.pop("_direct_input", None)
_panel_just_toggled = st.session_state.pop("_panel_just_toggled", False)
_has_patt = "pending_attachment" in st.session_state
typed = st.chat_input(
    "补充说明后发送，或直接发送…" if _has_patt else "输入数学题，支持 LaTeX 符号…"
)

# 确定是否"提交"：面板刚切换时强制跳过，避免误触发
_submitted = (not _panel_just_toggled) and (
    (typed is not None) or (_direct_input is not None) or bool(_similar_ctx) or bool(prefill)
)
_eff_text = _direct_input if _direct_input is not None else (typed if typed is not None else prefill)

# ── 取出附件（仅在发送时消费）────────────────────────────────────────────────
_patt_send = st.session_state.pop("pending_attachment", None) if _submitted else None

# ── 构造 user_input 和展示用 display_text ─────────────────────────────────────
user_input = None
display_text = None
_img_bytes = None

if _submitted:
    if _similar_ctx:
        user_input = "🎯 举一反三"
        display_text = "🎯 举一反三"
    elif _patt_send:
        att = _patt_send
        if att["type"] == "image":
            _img_bytes = att["bytes"]
            _img_b64_bubble = base64.b64encode(_compress_image(_img_bytes, max_size=400)).decode()
            user_input = _eff_text.strip() or "请解答图片中的数学题"
            display_text = ("📷 " + _eff_text.strip()) if _eff_text.strip() else "📷 图片题目"
        elif att["type"] == "file":
            _file_ctx = f"[文件：{att.get('name','')}]\n{att['content']}"
            user_input = (_file_ctx + "\n\n说明：" + _eff_text if _eff_text.strip() else _file_ctx)
            display_text = f"📄 {att.get('name','')}  {_eff_text}".strip()
    elif _eff_text:
        user_input = _eff_text
        display_text = _eff_text

# ── Agent 解题（渲染到 _new_turn 容器，确保在工具栏上方显示）──────────────────
if user_input:
    _sim_data = _similar_ctx if _similar_ctx else None
    _msg_record = {"role": "user", "content": display_text or user_input}
    if _img_bytes and "_img_b64_bubble" in dir():
        _msg_record["image_b64"] = _img_b64_bubble
    st.session_state.messages.append(_msg_record)

    with _new_turn:
        # 用户气泡
        _, _ub_col, _uav_col = st.columns([2, 5, 1])
        with _ub_col:
            _safe_disp = (display_text or user_input).replace("<", "&lt;").replace(">", "&gt;")
            _new_img_html = ""
            if _img_bytes and "_img_b64_bubble" in dir():
                _new_img_html = (
                    f'<img src="data:image/jpeg;base64,{_img_b64_bubble}" '
                    f'style="max-width:180px;border-radius:8px;margin-bottom:6px;display:block">'
                )
            st.markdown(
                f'<div class="msg-row-user"><div class="bubble-user">{_new_img_html}{_safe_disp}</div></div>',
                unsafe_allow_html=True,
            )
        with _uav_col:
            st.markdown('<div class="av av-user">👤</div>', unsafe_allow_html=True)

        # AI 回答
        _aav_col, _ai_col, _ = st.columns([1, 6, 1])
        with _aav_col:
            st.markdown('<div class="av av-ai">🧮</div>', unsafe_allow_html=True)
        with _ai_col:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages[:-1]
            ]
            trace_lines: list[str] = []
            _tool_start: dict[str, float] = {}
            _TOOL_LABELS = {
                "step_decomposer": "规划步骤",
                "formula_lookup":  "检索公式",
                "calculator":      "符号计算",
            }
            if _sim_data:
                solve_input = (
                    f"上一题：{_sim_data['question']}\n\n"
                    "请出一道相似但不同的练习题，标注题型和难度，只出题不解答。"
                )
                solve_history = []
            else:
                solve_input = user_input
                solve_history = history

            with st.status("思考中…", expanded=True) as status:
                def on_tool_call(name, args, result):
                    label = _TOOL_LABELS.get(name, name)
                    ts = datetime.now().strftime("%H:%M:%S")
                    if result is None:
                        _tool_start[name] = time.time()
                        status.update(label=f"{label}…")
                        trace_lines.append(f"[{ts}] {label}\n   参数: {args}")
                    else:
                        elapsed = time.time() - _tool_start.get(name, time.time())
                        preview = str(result)[:120] + ("…" if len(str(result)) > 120 else "")
                        trace_lines.append(f"   → {preview}  ({elapsed:.1f}s)\n")

                _solve_model = selected_model
                _use_guide = guide_mode and not _img_bytes and not _sim_data
                if _img_bytes:
                    if _secret("SILICONFLOW_API_KEY"):
                        _solve_model = "Qwen/Qwen3-VL-30B-A3B-Instruct"
                        status.update(label="切换视觉模型（Qwen VL）…")
                    elif _secret("GEMINI_API_KEY"):
                        # 有 Gemini key 就用 Gemini 视觉，无需额外 key
                        _solve_model = "gemini-2.0-flash"
                        status.update(label="切换视觉模型（Gemini）…")
                    else:
                        # 没有视觉 API，先 OCR 成文字再解题
                        status.update(label="识别图片内容…")
                        _ocr = ocr_math_image(_img_bytes)
                        if _ocr and not _ocr.startswith("（"):
                            solve_input = f"请解答以下题目：{_ocr}"
                            if user_input and user_input != "请解答图片中的数学题":
                                solve_input += f"\n（补充说明：{user_input}）"
                        _img_bytes = None  # 已转为文字，不再发图
                _agent = get_agent(use_local, _solve_model, guide_mode=_use_guide)

                buf = StringIO()
                sys.stdout = buf
                try:
                    stream = _agent.solve_stream(
                        solve_input, history=solve_history,
                        on_tool_call=on_tool_call, image_bytes=_img_bytes,
                    )
                    err = None
                except Exception as exc:
                    import traceback
                    stream, err = None, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
                finally:
                    sys.stdout = sys.__stdout__
                status.update(label="完成", state="complete", expanded=False)

            if stream is not None:
                ph = st.empty()
                collected: list[str] = []
                try:
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            collected.append(delta)
                            ph.markdown(fix_latex("".join(collected)) + "▌")
                    raw = "".join(collected)
                    raw, practice = extract_practice(raw)
                    clean_answer, tags = extract_tags(raw)
                    answer = fix_latex(clean_answer)
                    ph.markdown(answer)
                    if tags:
                        nk = "ktag_new"
                        sel = st.pills("知识点", tags, key=nk, label_visibility="collapsed")
                        if sel:
                            st.session_state.pop(nk, None)
                            st.session_state["prefill"] = f"请详细讲解「{sel}」"
                            st.rerun()
                    if practice:
                        st.markdown(
                            f'<p style="font-size:0.8rem;color:#888;margin:6px 0 2px">🧪 同类练习题</p>',
                            unsafe_allow_html=True,
                        )
                        if st.button(practice, key="practice_new", use_container_width=True):
                            st.session_state["_direct_input"] = practice
                            st.rerun()
                except Exception as e:
                    answer, tags, practice = f"流式输出出错：{e}", [], ""
                    ph.markdown(answer)
            else:
                answer, tags, practice = f"出错：{err}", [], ""
                st.markdown(answer)

            trace = "\n".join(trace_lines) or buf.getvalue().strip()
            if trace:
                with st.expander("工具调用详情", expanded=False):
                    st.code(trace, language="text")

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "tags": tags, "trace": trace,
        "practice": practice,
    })
