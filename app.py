"""
app.py — Math Solver Web UI

Launch:
  streamlit run app.py
  USE_LOCAL=1 streamlit run app.py
"""

import os, sys, base64, requests, re, time, random, hashlib, json, secrets as _secrets, contextlib
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import tempfile

from PIL import Image
import streamlit as st

for _k in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY",
           "OLLAMA_BASE_URL", "SUPABASE_URL", "SUPABASE_KEY"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from agent import MathAgent, CLOUD_PROVIDERS
from tools import get_and_clear_pending_images

# ── Supabase REST（直接用 requests，无需 supabase 包）────────────────────────
_SB_URL = os.environ.get(
    "SUPABASE_URL", ""
).rstrip("/") + "/rest/v1" if os.environ.get("SUPABASE_URL") else ""
_SB_KEY = os.environ.get("SUPABASE_KEY", "")
_SB_HDR = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Content-Type": "application/json",
}

def _sb_get(table: str, params: dict) -> list:
    if not _SB_URL or not _SB_KEY:
        return []
    try:
        r = requests.get(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
        return r.json() if r.ok else []
    except Exception:
        return []

def _sb_post(table: str, data: dict | list):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.post(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, timeout=8)
    except Exception:
        pass

def _sb_delete(table: str, params: dict):
    if not _SB_URL or not _SB_KEY:
        return
    try:
        requests.delete(f"{_SB_URL}/{table}", headers=_SB_HDR, params=params, timeout=8)
    except Exception:
        pass

def _sb_patch(table: str, data: dict, params: dict):
    try:
        requests.patch(f"{_SB_URL}/{table}", headers=_SB_HDR, json=data, params=params, timeout=8)
    except Exception:
        pass

# ── 学习记录（user_topics 表）────────────────────────────────────────────────
def _track_topic(email: str, course: str, topic: str):
    if not email:
        return
    existing = _sb_get("user_topics", {
        "user_email": f"eq.{email}", "topic": f"eq.{topic}", "select": "id,visit_count"
    })
    if existing:
        _sb_patch("user_topics",
                  {"visit_count": existing[0]["visit_count"] + 1,
                   "last_visited": datetime.now().isoformat()},
                  {"user_email": f"eq.{email}", "topic": f"eq.{topic}"})
    else:
        _sb_post("user_topics", {
            "user_email": email, "course": course, "topic": topic,
            "visit_count": 1, "last_visited": datetime.now().isoformat(),
        })

def _load_user_profile(email: str) -> dict:
    if not email:
        return {}
    rows = _sb_get("user_topics", {
        "user_email": f"eq.{email}", "select": "course,topic,visit_count,last_visited",
        "order": "visit_count.desc", "limit": "30",
    })
    if not rows:
        return {}
    weak   = [r for r in rows if r["visit_count"] >= 2][:6]
    recent = sorted(rows, key=lambda r: r.get("last_visited") or "", reverse=True)[:5]
    return {"weak": weak, "recent": recent, "all": rows}

# ── 用户管理（登录注册 + 7天免登录）──────────────────────────────────────────
_TOKEN_DAYS = 7

def _hash_pw(pw: str) -> str:
    salt = _secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"

def _check_pw(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex() == h
    except Exception:
        return hashlib.sha256(pw.encode()).hexdigest() == stored

def _user_exists(email: str) -> bool:
    return len(_sb_get("users", {"email": f"eq.{email}", "select": "email"})) > 0

def _check_user(email: str, pw: str) -> bool:
    rows = _sb_get("users", {
        "email": f"eq.{email}", "select": "email,password_hash"
    })
    if not rows:
        return False
    return _check_pw(pw, rows[0]["password_hash"])

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
    return _sb_get("wrong_book", {"email": f"eq.{email}", "select": "*", "order": "id"})

def _save_wrong_book(email: str, wb: list):
    if not email:
        return
    rows = [
        {
            "email": email,
            "question": item["question"],
            "saved_at": item.get("saved_at", ""),
            "image_b64": item.get("image_b64", ""),
        }
        for item in wb
    ] if wb else []
    # 先备份现有数据，delete 后 insert 失败时可以恢复
    try:
        _backup = _load_wrong_book(email)
    except Exception:
        _backup = []
    try:
        _sb_delete("wrong_book", {"email": f"eq.{email}"})
        if rows:
            _sb_post("wrong_book", rows)
    except Exception:
        # insert 失败，尝试恢复备份数据
        if _backup:
            try:
                _sb_delete("wrong_book", {"email": f"eq.{email}"})
                _sb_post("wrong_book", [
                    {"email": email, "question": x["question"],
                     "saved_at": x.get("saved_at", ""), "image_b64": x.get("image_b64", "")}
                    for x in _backup
                ])
            except Exception:
                pass

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
            _lockout_until = st.session_state.get("_login_lockout_until", 0)
            _locked = time.time() < _lockout_until
            if _locked:
                _wait_secs = int(_lockout_until - time.time()) + 1
                st.error(f"密码错误次数过多，请等待 {_wait_secs} 秒后重试")
            if st.button("登录", type="primary", use_container_width=True, key="do_login", disabled=_locked):
                if _check_user(_em, _pw):
                    st.session_state["_login_attempts"] = 0
                    st.session_state["_login_lockout_until"] = 0
                    _tok = _create_token(_em)
                    st.query_params["_auth"] = _tok
                    st.session_state["logged_in"] = True
                    st.session_state["user_email"] = _em
                    st.session_state["_token"] = _tok
                    # 同时写 localStorage，关闭浏览器后也能恢复
                    _cv1.html(
                        f'<script>try{{window.parent.localStorage.setItem("ma_auth_tok","{_tok}");}}catch(e){{}}</script>',
                        height=1,
                    )
                    st.rerun()
                else:
                    _attempts = st.session_state.get("_login_attempts", 0) + 1
                    st.session_state["_login_attempts"] = _attempts
                    if _attempts >= 5:
                        st.session_state["_login_lockout_until"] = time.time() + 60
                        st.session_state["_login_attempts"] = 0
                        st.error("密码连续错误5次，请等待1分钟后重试")
                    else:
                        st.error(f"邮箱或密码不正确（还有 {5 - _attempts} 次机会）")
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

# ── localStorage 读取（关闭浏览器后用桌面快捷打开也能恢复登录）─────────────
# 总是渲染，让 Streamlit 组件树稳定；JS 内部判断是否需要注入
import streamlit.components.v1 as _cv1
_cv1.html("""
<script>
(function() {
try {
    // ── 1. localStorage 自动登录 ──────────────────────────────────
    var url = new URL(window.parent.location.href);
    if (!url.searchParams.get('_auth')) {
        var t = window.parent.localStorage.getItem('ma_auth_tok');
        if (t) {
            url.searchParams.set('_auth', t);
            window.parent.history.replaceState(null, '', url.toString());
            setTimeout(function() {
                if (!new URL(window.parent.location.href).searchParams.get('_auth')) return;
                window.parent.sessionStorage.setItem("ma_reloaded", "1");
                window.parent.location.replace(url.toString());
            }, 800);
        }
    }
    }

    // ── 2. 睡眠唤醒后自动重连 ────────────────────────────────────
    // 记录最后一次页面可见时间
    var _lastVisible = Date.now();
    var SLEEP_RELOAD_MS = 90 * 1000;  // 超过 90 秒不可见唤醒后重载

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            _lastVisible = Date.now();
        } else {
            var slept = Date.now() - _lastVisible;
            if (slept > SLEEP_RELOAD_MS) {
                // 保留 URL 参数（含 _auth token），只刷新页面
                window.parent.location.reload();
            }
        }
    });

} catch(e) {}
})();
</script>
""", height=1)

# ── KaTeX 数学公式渲染（比 Streamlit 内置 MathJax 更稳定）────────────────────
_cv1.html("""
<script>
(function() {
try {
    var doc = window.parent.document;
    if (doc.getElementById('_katex_css')) return;  // 避免重复加载

    var link = doc.createElement('link');
    link.id = '_katex_css';
    link.rel = 'stylesheet';
    link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css';
    doc.head.appendChild(link);

    function loadScript(src, onload) {
        var s = doc.createElement('script');
        s.src = src;
        s.onload = onload;
        doc.head.appendChild(s);
    }

    loadScript('https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js', function() {
        loadScript('https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js', function() {
            var _timer = null;
            function doRender() {
                try {
                    renderMathInElement(doc.body, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$',  right: '$',  display: false},
                            {left: '\\[', right: '\\]', display: true},
                            {left: '\\(', right: '\\)', display: false}
                        ],
                        throwOnError: false,
                        trust: true
                    });
                } catch(e) {}
            }
            doRender();
            // Streamlit 每次重渲染后自动补充 render
            var obs = new MutationObserver(function() {
                clearTimeout(_timer);
                _timer = setTimeout(doRender, 250);
            });
            obs.observe(doc.body, {childList: true, subtree: true});
        });
    });
} catch(e) {}
})();
</script>
""", height=1)

# ── 手机端汉堡菜单（侧边栏滑出覆盖层）──────────────────────────────────────
_cv1.html("""
<script>
(function() {
try {
    var doc = window.parent.document;
    if (doc.getElementById('ma-hamburger')) return;  // 避免重复注入

    // ── 汉堡按钮 ──────────────────────────────────────────────────────────
    var btn = doc.createElement('div');
    btn.id = 'ma-hamburger';
    btn.innerHTML = '&#9776;';  // ☰
    doc.body.appendChild(btn);

    // ── 半透明遮罩 ────────────────────────────────────────────────────────
    var backdrop = doc.createElement('div');
    backdrop.id = 'ma-backdrop';
    doc.body.appendChild(backdrop);

    function getSidebar() {
        return doc.querySelector('[data-testid="stSidebar"]');
    }

    function openSidebar() {
        var sb = getSidebar();
        if (sb) sb.classList.add('ma-sb-open');
        backdrop.classList.add('active');
        btn.innerHTML = '&#10005;';  // ✕
    }

    function closeSidebar() {
        var sb = getSidebar();
        if (sb) sb.classList.remove('ma-sb-open');
        backdrop.classList.remove('active');
        btn.innerHTML = '&#9776;';  // ☰
    }

    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var sb = getSidebar();
        if (sb && sb.classList.contains('ma-sb-open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    // 点遮罩关闭
    backdrop.addEventListener('click', closeSidebar);

    // 点侧边栏里的按钮后延迟关闭（给 Streamlit 时间处理点击）
    doc.addEventListener('click', function(e) {
        var sb = getSidebar();
        if (!sb || !sb.classList.contains('ma-sb-open')) return;
        if (e.target === btn) return;
        if (sb.contains(e.target)) {
            setTimeout(closeSidebar, 200);
        }
    });

    // 暗色模式下汉堡按钮样式
    function applyDarkHamburger() {
        var isDark = doc.documentElement.getAttribute('data-theme') === 'dark'
            || doc.body.style.background === 'rgb(15, 15, 23)'
            || doc.querySelector('.stApp') &&
               getComputedStyle(doc.querySelector('.stApp')).backgroundColor === 'rgb(15, 15, 23)';
        if (isDark) {
            btn.style.background = 'rgba(24,24,42,0.95)';
            btn.style.borderColor = '#32325a';
            btn.style.color = '#dde0f5';
        } else {
            btn.style.background = 'rgba(255,255,255,0.93)';
            btn.style.borderColor = '#D4CEC8';
            btn.style.color = '#333';
        }
    }
    applyDarkHamburger();
    // 切换主题时更新按钮颜色
    new MutationObserver(applyDarkHamburger).observe(doc.body, {attributes: true, subtree: false});

} catch(e) {}
})();
</script>
""", height=1)

# ── URL 参数持久化（7 天免登录）──────────────────────────────────────────────
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
        # 同步清除 localStorage，防止过期 token 导致无限 reload
        _cv1.html(
            '<script>try{window.parent.localStorage.removeItem("ma_auth_tok");}catch(e){}</script>',
            height=1,
        )

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
@import url('https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
/* AI 回复区域使用霞鹜文楷手写体 */
.bubble-asst-inner { font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif; font-size: 1rem; line-height: 1.8; }

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

/* ── Streamlit 顶栏：与页面背景融合，保留侧栏开关 ── */
header[data-testid="stHeader"] {
    background: #F5F0EB !important;
    box-shadow: none !important;
    border-bottom: none !important;
}
/* 只隐藏顶部彩色装饰条，不隐藏工具栏 */
header[data-testid="stHeader"] [data-testid="stDecoration"] {
    display: none !important;
}
.main .block-container { padding-top: 0.5rem !important; }

/* ── 课程横幅 ── */
.course-banner {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; margin-bottom: 12px;
    background: #EEE8E1; border-radius: 8px;
    font-size: 0.9rem; font-weight: 600; color: #555;
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

/* ── 用户气泡（右对齐，无头像）── */
.msg-row-user {
    display: flex;
    justify-content: flex-end;
    margin: 6px 0 6px;
}
.bubble-user {
    background: #95EC69;
    color: #111;
    border-radius: 18px 4px 18px 18px;
    padding: 10px 14px;
    word-break: break-word;
    line-height: 1.6;
    font-size: 0.95rem;
    display: inline-block;
    max-width: 72%;
}
/* ── AI 回答（左对齐，无头像，全宽）── */
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
.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div {
    background: #FFFFFF;
    border-radius: 4px 18px 18px 18px;
    padding: 10px 14px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    font-family: 'LXGW WenKai', 'KaiTi', 'STKaiti', serif;
    font-size: 1rem;
    line-height: 1.8;
    word-break: break-word;
}

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

/* ── 输入框：外框即输入区，内部 textarea 透明（去掉套娃黑块）── */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: #EDE5DC !important; }
[data-testid="stChatInputContainer"] {
    background: #FFFFFF !important;
    border: 1.5px solid #C8C0B8 !important;
    border-radius: 24px !important;
    padding: 8px 14px 8px !important;
    margin: 0 0 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07) !important;
}
[data-testid="stChatInputContainer"]:focus-within {
    border-color: #2aae67 !important;
    box-shadow: 0 0 0 2px rgba(42,174,103,0.15) !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    color: #1a1a1a !important;
    font-size: 0.95rem !important;
    padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}
[data-testid="stChatInputSubmitButton"] button {
    background: #2aae67 !important; border-radius: 50% !important;
}
/* ── 工具栏与横幅：随内容区等宽，sticky 吸附在输入框上方 ── */
[data-testid="stHorizontalBlock"]:has(.toolbar-btn) {
    position: sticky !important;
    bottom: 72px !important;
    z-index: 200 !important;
    background: #EDE5DC !important;
    padding: 4px 0 2px !important;
    margin: 0 !important;
}
.course-banner-row [data-testid="stHorizontalBlock"],
[data-testid="stHorizontalBlock"]:has(.course-banner) {
    align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has(.course-banner) [data-testid="stButton"] button {
    height: 100% !important; min-height: 42px !important;
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

/* ── KaTeX 公式样式（课本感）── */
.katex-display {
    margin: 0.8em 0 !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
}
.katex { font-size: 1.05em !important; }
.katex-display > .katex { font-size: 1.1em !important; }

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
    /* 侧边栏：改为左滑覆盖层，默认隐藏在屏幕左侧 */
    [data-testid="stSidebar"] {
        display: block !important;
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        width: 82vw !important; max-width: 300px !important;
        height: 100vh !important;
        z-index: 9998 !important;
        overflow-y: auto !important;
        transform: translateX(-110%) !important;
        transition: transform 0.26s cubic-bezier(.4,0,.2,1) !important;
    }
    [data-testid="stSidebar"].ma-sb-open {
        transform: translateX(0) !important;
        box-shadow: 6px 0 32px rgba(0,0,0,0.32) !important;
    }
    /* 汉堡按钮 */
    #ma-hamburger {
        display: flex !important;
        position: fixed !important;
        top: 10px !important; left: 10px !important;
        z-index: 9999 !important;
        width: 40px !important; height: 40px !important;
        background: rgba(255,255,255,0.93) !important;
        border: 1px solid #D4CEC8 !important;
        border-radius: 11px !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
        font-size: 1.2rem !important;
        user-select: none !important;
        -webkit-tap-highlight-color: transparent !important;
    }
    /* 半透明遮罩 */
    #ma-backdrop {
        display: none;
        position: fixed !important;
        inset: 0 !important;
        background: rgba(0,0,0,0.42) !important;
        z-index: 9997 !important;
        -webkit-tap-highlight-color: transparent !important;
    }
    #ma-backdrop.active { display: block !important; }
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
def _secret(key):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")

# ── 课程知识点索引 ────────────────────────────────────────────────────────────
_COURSE_TOPICS = {
    "数学分析": ["ε-δ极限定义", "连续性与间断点", "导数与微分", "中值定理族", "Taylor展开", "黎曼积分", "级数收敛判别", "多元函数极值", "重积分", "曲线与曲面积分"],
    "高等代数": ["行列式计算", "矩阵的秩", "线性方程组", "向量空间", "线性变换", "特征值与特征向量", "二次型化标准形", "Jordan标准形"],
    "解析几何": ["向量代数运算", "空间直线方程", "平面方程", "直线与平面位置关系", "二次曲面分类", "坐标变换"],
    "常微分方程": ["一阶ODE解法", "高阶线性ODE", "常系数齐次方程", "常系数非齐次方程", "幂级数解法", "方程组与矩阵指数", "稳定性分析"],
    "复变函数": ["复数与复平面", "解析函数", "Cauchy-Riemann方程", "复积分", "Cauchy积分定理", "Laurent展开", "留数定理", "保角映射"],
    "抽象代数": ["群的基本概念", "子群与陪集", "正规子群与商群", "同态与同构", "环与理想", "域扩张", "Galois理论基础"],
    "概率论": ["古典概型", "条件概率与独立性", "随机变量与分布", "常见离散分布", "常见连续分布", "期望与方差", "特征函数", "大数定律", "中心极限定理"],
    "实变函数": ["集合与基数", "测度的构造", "可测函数", "Lebesgue积分", "三大收敛定理", "L^p空间"],
    "泛函分析": ["度量空间", "赋范线性空间", "Banach空间", "Hilbert空间", "有界线性算子", "开映射与闭图像定理", "谱理论"],
    "点集拓扑": ["拓扑空间与基", "连续映射", "紧致性", "连通性", "分离公理", "乘积拓扑", "商拓扑"],
    "微分几何": ["曲线的Frenet标架", "曲率与挠率", "曲面的第一基本形式", "第二基本形式", "高斯曲率与平均曲率", "测地线", "Gauss-Bonnet定理"],
    "数值分析": ["插值与逼近", "数值积分", "线性方程组直接法", "迭代法收敛性", "非线性方程求根", "常微分方程数值解", "误差与稳定性"],
    "偏微分方程": ["一阶PDE特征线法", "波动方程", "热传导方程", "Laplace与Poisson方程", "分离变量法", "Fourier变换法", "Green函数"],
    "数学建模": ["微分方程建模", "种群与传染病模型", "优化与线性规划", "图论与网络模型", "统计回归分析", "排队论", "差分方程"],
}

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
    # 去除模型可能输出的多余 HTML 标签（Gemini 有时会在末尾加 </div> 等）
    text = re.sub(r'</?(div|span|p|br|html|body)[^>]*>', '', text, flags=re.IGNORECASE)

    # \[ ... \] → $$ ... $$（块公式）
    text = re.sub(r'\\\[\s*(.*?)\s*\\\]', r'\n$$\1$$\n', text, flags=re.DOTALL)
    # \( ... \) → $ ... $（行内公式）
    text = re.sub(r'\\\(\s*(.*?)\s*\\\)', r'$\1$', text, flags=re.DOTALL)

    # 行内 $ ... $ 里含矩阵/多行环境时，升级为块级 $$ ... $$
    # 防止 & 和 \\ 被 markdown 解析破坏
    # 注：不用 re.DOTALL，限制匹配在单行内，避免跨段落回溯（ReDoS）
    def _upgrade_matrix(m):
        inner = m.group(1)
        if r'\begin{' in inner:
            return f'\n$$\n{inner}\n$$\n'
        return m.group(0)
    text = re.sub(r'\$(?!\$)([^\$]{1,2000}?)\$(?!\$)', _upgrade_matrix, text)

    # 修复奇数个 $$（未关闭的块公式）
    if text.count('$$') % 2 != 0:
        text += '\n$$'

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
    """拍题 OCR：用 SiliconFlow Qwen-VL 识别图片中的数学题文字。"""
    key = _secret("SILICONFLOW_API_KEY")
    if not key:
        return "（未配置 SILICONFLOW_API_KEY，无法识别图片）"
    try:
        from agent import MathAgent
        agent = MathAgent(use_local=False, model="Qwen/Qwen3-VL-30B-A3B-Instruct")
        result = agent.solve(
            "请识别图片中的数学题，只输出题目原文，不要解答",
            image_bytes=image_bytes,
        )
        if hasattr(result, '__iter__') and not isinstance(result, str):
            return "".join(c.choices[0].delta.content or "" for c in result)
        return result
    except Exception as e:
        return f"识别失败：{e}"


def transcribe_audio(audio_file) -> tuple[str, str]:
    """语音转文字，使用 SiliconFlow SenseVoiceSmall（中英文优化）。"""
    raw = audio_file.read()
    mime = "audio/webm"
    if raw[:4] == b"RIFF":
        mime = "audio/wav"
    elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
        mime = "audio/mp3"
    elif len(raw) > 8 and raw[4:8] == b"ftyp":
        mime = "audio/mp4"
    elif raw[:4] == b"OggS":
        mime = "audio/ogg"

    # SiliconFlow SenseVoiceSmall（中英文专优）
    sf_key = _secret("SILICONFLOW_API_KEY")
    if sf_key:
        try:
            ext = mime.split("/")[-1].replace("webm", "webm").replace("mp4", "m4a")
            resp = requests.post(
                "https://api.siliconflow.cn/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {sf_key}"},
                files={"file": (f"audio.{ext}", raw, mime)},
                data={"model": "FunAudioLLM/SenseVoiceSmall"},
                timeout=30,
            )
            data = resp.json()
            if "text" in data and data["text"].strip():
                return data["text"].strip(), ""
            if "error" in data:
                pass
        except Exception:
            pass

    return "", "请在 Streamlit Cloud Secrets 配置 SILICONFLOW_API_KEY"

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
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ── 暗色模式 CSS 覆盖 ─────────────────────────────────────────────────────────
if st.session_state.dark_mode:
    st.markdown("""
<style>
/* ═══ 夜间模式 — 深海蓝调 ═══ */
:root {
    --dm-bg:        #0f0f17;
    --dm-panel:     #18182a;
    --dm-card:      #20203a;
    --dm-card2:     #252540;
    --dm-border:    #32325a;
    --dm-text:      #dde0f5;
    --dm-muted:     #7070a0;
    --dm-accent:    #5a8cff;
    --dm-user-bg:   #1a3a5e;
    --dm-user-text: #a8d0f0;
    --dm-user-av:   #1e4880;
}

/* ══ 全局背景 & 文字 ══ */
html, body { background: var(--dm-bg) !important; }
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], [data-testid="block-container"],
section.main, .main, .block-container, footer,
[data-testid="stBottom"], .stBottom,
[data-testid="stBottomBlockContainer"],
[class*="bottom"], [class*="Bottom"] { background: var(--dm-bg) !important; }
p, span, label, div, li, td, th, h1, h2, h3, h4, h5, h6 { color: var(--dm-text) !important; }

/* ══ 侧边栏 ══ */
[data-testid="stSidebar"] {
    background: var(--dm-panel) !important;
    border-right: 1px solid var(--dm-border) !important;
}
[data-testid="stSidebar"] * { color: var(--dm-text) !important; }
[data-testid="stSidebar"] .stButton button {
    background: var(--dm-card) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: var(--dm-card2) !important; color: #fff !important;
    border-color: var(--dm-accent) !important;
}

/* ══ 顶栏 ══ */
header[data-testid="stHeader"] { background: var(--dm-panel) !important; }

/* ══ 课程横幅 & 退出按钮容器 ══ */
.course-banner { background: var(--dm-card) !important; color: var(--dm-muted) !important; }
[data-testid="stHorizontalBlock"] { background: transparent !important; }
[data-testid="stColumn"] { background: transparent !important; }

/* ══ 用户气泡 — 深蓝调代替微信绿 ══ */
.bubble-user {
    background: var(--dm-user-bg) !important;
    color: var(--dm-user-text) !important;
    border-radius: 18px 4px 18px 18px !important;
}

/* ══ AI 气泡 ══ */
.stMarkdown:has(.asst-bubble-marker) + .stMarkdown > div {
    background: var(--dm-card) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.6) !important;
    color: var(--dm-text) !important;
}
.bubble-asst-wrap {
    background: var(--dm-card) !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.6) !important;
}
.bubble-asst-wrap p, .bubble-asst-wrap li { color: var(--dm-text) !important; }

/* ══ 代码块（文字思维导图等）══ */
pre, pre code, code {
    background: #12122a !important;
    color: #b8c8e8 !important;
    border: 1px solid var(--dm-border) !important;
}
[data-testid="stCodeBlock"], [data-testid="stCode"],
[data-testid="stCodeBlock"] > div, [data-testid="stCode"] > div,
.stCodeBlock, .stCodeBlock > div { background: #12122a !important; }
[data-testid="stCodeBlock"] pre, [data-testid="stCode"] pre { background: #12122a !important; }
/* 代码块复制按钮 */
[data-testid="stCodeBlock"] button, [data-testid="stCode"] button {
    background: var(--dm-card) !important; color: var(--dm-muted) !important;
    border: 1px solid var(--dm-border) !important;
}

/* ══ 思维导图/函数图像（matplotlib PNG）── 轻度暗化 ══ */
.stMarkdown img, [data-testid="stMarkdownContainer"] img {
    filter: brightness(0.88) contrast(1.05) !important;
    border-color: var(--dm-border) !important;
    border-radius: 6px !important;
}

/* ══ 示例卡片 ══ */
[data-testid="stVerticalBlock"] [data-testid="stButton"] button {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3) !important;
}
[data-testid="stVerticalBlock"] [data-testid="stButton"] button:hover {
    background: var(--dm-card2) !important;
    border-color: var(--dm-accent) !important; color: #fff !important;
}

/* ══ 功能卡片 ══ */
.feature-card { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
.feature-title { color: var(--dm-text) !important; }
.feature-desc { color: var(--dm-muted) !important; }

/* ══ 欢迎语 ══ */
.greeting-main, .welcome-title { color: var(--dm-text) !important; }
.greeting-sub, .welcome-sub { color: var(--dm-muted) !important; }

/* ══ 输入框 & 底栏（去掉套娃黑块：外框为可见盒子，内部 textarea 透明）══ */
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div { background: var(--dm-bg) !important; }
[data-testid="stChatInputContainer"] {
    background: var(--dm-panel) !important;
    border: 1.5px solid var(--dm-border) !important;
    border-radius: 24px !important;
    padding: 8px 14px 8px !important;
    margin: 0 0 10px !important;
    box-shadow: none !important;
}
[data-testid="stChatInputContainer"]:focus-within {
    border-color: var(--dm-accent) !important;
    box-shadow: 0 0 0 2px rgba(90,140,255,0.2) !important;
}
[data-testid="stChatInputTextArea"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    color: var(--dm-text) !important;
    padding: 2px 0 !important;
}
[data-testid="stChatInputTextArea"]:focus {
    box-shadow: none !important; border: none !important;
}
[data-testid="stChatInputSubmitButton"] button { background: #2a6edd !important; }
/* 工具栏 sticky */
[data-testid="stHorizontalBlock"]:has(.toolbar-btn) {
    background: var(--dm-bg) !important;
}

/* ══ 文件上传 ══ */
[data-testid="stFileUploaderDropzone"] button,
[data-testid="stFileUploadDropzone"] button {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-testid="stFileUploaderDropzone"] button:hover,
[data-testid="stFileUploadDropzone"] button:hover {
    background: var(--dm-card2) !important; border-color: var(--dm-accent) !important;
}
[data-testid="stFileUploaderFileName"] { color: var(--dm-text) !important; }

/* ══ Selectbox / 下拉菜单 ══ */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: var(--dm-panel) !important;
    border: 1px solid var(--dm-border) !important;
    color: var(--dm-text) !important;
}
[data-baseweb="popover"], [data-baseweb="menu"],
[data-baseweb="menu"] ul, [data-baseweb="list"] { background: var(--dm-panel) !important; }
[data-baseweb="menu"] li, [data-baseweb="option"] { color: var(--dm-text) !important; }
[data-baseweb="menu"] li:hover, [data-baseweb="option"]:hover { background: var(--dm-card2) !important; }

/* ══ Plus 面板 ══ */
.plus-panel { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
.plus-panel .stButton button {
    background: var(--dm-card) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
.plus-panel .stButton button:hover {
    background: var(--dm-card2) !important; border-color: var(--dm-accent) !important;
}

/* ══ 工具栏 ══ */
.toolbar-model [data-testid="stSelectbox"] > div > div {
    background: rgba(24,24,42,0.98) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
.toolbar-btn button { color: var(--dm-muted) !important; }
.toolbar-btn button:hover { background: var(--dm-card) !important; color: var(--dm-text) !important; }

/* ══ 麦克风 ══ */
[data-testid="stAudioInput"],
[data-testid="stAudioInput"] > div {
    background: var(--dm-panel) !important; border-color: var(--dm-border) !important;
}
[data-testid="stAudioInput"] button { color: var(--dm-muted) !important; }

/* ══ 语音/文字输入 ══ */
[data-testid="stTextArea"] textarea {
    background: var(--dm-panel) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}

/* ══ Guide Chip ══ */
.guide-chip { background: var(--dm-card) !important; border-color: var(--dm-border) !important; color: var(--dm-muted) !important; }
.guide-chip.on { background: #2a6edd !important; border-color: #2a6edd !important; color: #fff !important; }

/* ══ Checkbox / Toggle ══ */
[data-testid="stCheckbox"] span, [data-testid="stCheckbox"] p { color: var(--dm-text) !important; }
[data-testid="stToggle"] { color: var(--dm-text) !important; }

/* ══ Info / Warning / Error 提示块 ══ */
[data-testid="stAlert"] { background: var(--dm-card) !important; border-color: var(--dm-border) !important; }
[data-testid="stAlert"] p { color: var(--dm-text) !important; }

/* ══ Expander ══ */
[data-testid="stExpander"] { background: var(--dm-panel) !important; border-color: var(--dm-border) !important; }
[data-testid="stExpander"] summary { color: var(--dm-text) !important; }
details, details summary { background: var(--dm-panel) !important; color: var(--dm-text) !important; }

/* ══ 分割线 & 小字 ══ */
hr { border-color: var(--dm-border) !important; }
small, .caption { color: var(--dm-muted) !important; }

/* ══ 登录页 ══ */
.login-logo-title { color: var(--dm-text) !important; }
.login-logo-sub { color: var(--dm-muted) !important; }

/* ══ Pills（知识点标签）══ */
div[data-testid="stPills"] button {
    background: var(--dm-card) !important;
    border-color: var(--dm-border) !important; color: var(--dm-text) !important;
}
div[data-testid="stPills"] button:hover,
div[data-testid="stPills"] button[aria-selected="true"] {
    background: var(--dm-accent) !important; color: #fff !important;
}

/* ══ 元素容器通用 ══ */
[data-testid="element-container"] { background: transparent !important; }

/* ══ KaTeX 暗色适配 ══ */
.katex-display { background: transparent !important; color: #dde0f5 !important; }
.katex, .katex * { color: #dde0f5 !important; background: transparent !important; }
.katex .fbox, .katex .fbox > .katex-html { border-color: #7a7ab8 !important; background: transparent !important; }
.katex .frac-line { background: #dde0f5 !important; border-color: #dde0f5 !important; }
.katex svg path, .katex .svg-align path { fill: #dde0f5 !important; stroke: #dde0f5 !important; }
.katex .delimsizing path, .katex .stretchy path { fill: #dde0f5 !important; }

/* ══ MathJax 3（Streamlit 内置）暗色适配 ══ */
mjx-container { background: transparent !important; color: #dde0f5 !important; }
mjx-container * { color: #dde0f5 !important; background: transparent !important; }
mjx-container svg, mjx-container svg * { fill: #dde0f5 !important; }
mjx-container[jax="CHTML"] { color: #dde0f5 !important; }
/* \boxed{} 边框 */
mjx-menclose { border-color: #7a7ab8 !important; }
mjx-mfrac > mjx-frac > mjx-line { border-color: #dde0f5 !important; }

/* ══ MathJax 2 降级兼容 ══ */
.MathJax_Display, .MathJax, .MJXc-display { background: transparent !important; color: #dde0f5 !important; }
.MathJax svg { fill: #dde0f5 !important; }

/* ══ Streamlit 数学块容器 ══ */
.stMarkdownContainer .math, .stMarkdown .math { background: transparent !important; }
[data-testid="stMarkdownContainer"] > div { background: transparent !important; }
</style>
""", unsafe_allow_html=True)

    # 把暗色覆盖 CSS 注入到父页面 <head>，绕过 React 重渲染覆盖问题
    _cv1.html("""<script>
(function() {
    try {
        var doc = window.parent.document;
        var existing = doc.getElementById('_dm_override_css');
        var s = existing || doc.createElement('style');
        if (!existing) { s.id = '_dm_override_css'; doc.head.appendChild(s); }
        s.textContent = [
                /* 底栏 */
                '[data-testid="stBottom"]{background:#0f0f17!important}',
                '[data-testid="stBottomBlockContainer"]{background:#0f0f17!important}',
                '[data-testid="stBottom"]>div{background:#0f0f17!important}',
                /* 输入框外框变深色 */
                '[data-testid="stChatInputContainer"]{background:#18182a!important;border:1.5px solid #32325a!important;border-radius:24px!important;box-shadow:none!important}',
                '[data-testid="stChatInput"]{background:#0f0f17!important}',
                /* textarea 透明 */
                '[data-testid="stChatInputTextArea"]{background:transparent!important;border:none!important;box-shadow:none!important;color:#dde0f5!important}',
                /* placeholder */
                '[data-testid="stChatInputTextArea"]::placeholder{color:#5050708!important}',
                /* 发送按钮 */
                '[data-testid="stChatInputSubmitButton"] button{background:#2a6edd!important}',
                /* KaTeX 暗色 */
                '.katex,.katex *{color:#dde0f5!important;background:transparent!important}',
                '.katex-display{background:transparent!important;color:#dde0f5!important}',
                '.katex .frac-line{background:#dde0f5!important;border-color:#dde0f5!important}',
                '.katex .fbox{border-color:#7a7ab8!important;background:transparent!important}',
                '.katex svg path,.katex .svg-align path,.katex .delimsizing path,.katex .stretchy path{fill:#dde0f5!important;stroke:#dde0f5!important}',
                /* MathJax 3 暗色 */
                'mjx-container,mjx-container *{color:#dde0f5!important;background:transparent!important}',
                'mjx-container svg,mjx-container svg *{fill:#dde0f5!important}',
                'mjx-menclose{border-color:#7a7ab8!important}',
                'mjx-mfrac>mjx-frac>mjx-line{border-color:#dde0f5!important}',
                /* MathJax 2 兼容 */
                '.MathJax_Display,.MathJax,.MJXc-display{background:transparent!important;color:#dde0f5!important}',
                '.MathJax svg{fill:#dde0f5!important}',
                /* Streamlit 数学容器 */
                '.stMarkdownContainer .math,.stMarkdown .math{background:transparent!important}',
                '[data-testid="stMarkdownContainer"]>div{background:transparent!important}',
            ].join('');
    } catch(e) {}
})();
</script>""", height=1)


# ── 侧边栏 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # ── 用户信息 + 退出 ──────────────────────────────────────────────────────
    _uemail = st.session_state.get("user_email", "")
    st.markdown(
        f'<p style="font-size:0.75rem;color:#888;margin:0 0 4px">👤 {_uemail}</p>',
        unsafe_allow_html=True,
    )
    _sb_top_left, _sb_top_right = st.columns([3, 1])
    with _sb_top_left:
        if st.button("退出登录", key="logout_btn", use_container_width=True):
            _tok = st.session_state.pop("_token", None)
            if _tok:
                _invalidate_token(_tok)
            try:
                del st.query_params["_auth"]
            except Exception:
                pass
            _cv1.html(
                '<script>try{window.parent.localStorage.removeItem("ma_auth_tok");}catch(e){}</script>',
                height=1,
            )
            st.session_state["logged_in"] = False
            st.session_state.pop("user_email", None)
            st.rerun()
    with _sb_top_right:
        _dm_icon = "☀️" if st.session_state.dark_mode else "🌙"
        if st.button(_dm_icon, key="dark_mode_btn", use_container_width=True, help="切换深色/浅色模式"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
    st.divider()

    # ── 最近问题（最多显示20条）─────────────────────────────────────────────────
    _user_msgs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if _user_msgs:
        st.markdown('<p style="font-size:0.75rem;color:#888;margin:0 0 6px">最近问题</p>',
                    unsafe_allow_html=True)
        for _qi, _q in enumerate(_user_msgs[-20:]):
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
                        _wb_img = wp.get("image_b64", "")
                        if _wb_img:
                            # 恢复图片为待发附件，用户可补充文字后发送
                            _img_bytes_wb = base64.b64decode(_wb_img)
                            st.session_state["pending_attachment"] = {
                                "type": "image", "bytes": _img_bytes_wb, "name": "错题图片"
                            }
                            _txt = wp["question"].lstrip("📷").strip()
                            if _txt and _txt != "图片题目":
                                st.session_state["prefill"] = _txt
                        else:
                            st.session_state["prefill"] = wp["question"]
                        st.rerun()
                with c2:
                    if st.button("删除", key=f"wb_del_{wi}", use_container_width=True):
                        st.session_state.wrong_book.pop(wi)
                        _save_wrong_book(_uemail, st.session_state.wrong_book)
                        st.rerun()

    # ── 学习档案 ────────────────────────────────────────────────────────────────
    if "user_profile" not in st.session_state:
        st.session_state["user_profile"] = _load_user_profile(_uemail)
    _profile = st.session_state.get("user_profile", {})
    if _profile:
        with st.expander("📊 学习档案", expanded=False):
            _weak = _profile.get("weak", [])
            _recent = _profile.get("recent", [])
            if _weak:
                st.caption("⚠️ 薄弱点（多次学习）")
                for _w in _weak:
                    _label = f"{_w['topic']} ×{_w['visit_count']}"
                    if st.button(_label, key=f"weak_{_w['topic']}", use_container_width=True):
                        st.session_state["current_course"] = _w.get("course", "")
                        st.session_state.messages = []
                        st.session_state["_direct_input"] = (
                            f"【知识点讲解】{_w.get('course','')} · {_w['topic']}"
                        )
                        st.rerun()
            if _recent:
                st.caption("🕐 最近学过")
                for _r in _recent[:4]:
                    st.markdown(f"- {_r.get('course','')} · **{_r['topic']}**",
                                unsafe_allow_html=False)

    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state["_confirm_clear"] = True
        st.rerun()
    if st.session_state.get("_confirm_clear"):
        st.warning("确定要清空全部对话记录吗？")
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            if st.button("确定清空", key="confirm_yes", use_container_width=True, type="primary"):
                st.session_state.messages = []
                st.session_state.pop("prefill", None)
                st.session_state.pop("_confirm_clear", None)
                st.rerun()
        with _cc2:
            if st.button("取消", key="confirm_no", use_container_width=True):
                st.session_state.pop("_confirm_clear", None)
                st.rerun()

    st.divider()
    with st.expander("📖 使用手册", expanded=False):
        st.markdown("""
**🧮 Math Agent 使用指南**

---

**提问方式**

- **文字**：直接在底部输入框输入题目，支持 LaTeX 符号（如 `$x^2$`、`\\int`）
- **拍题**：点 ➕ → 拍照 / 上传图片，AI 自动识别并解答
- **语音**：点左下角 🎙️ 录音，识别完成后在文本框确认发送
- **示例题**：首页六道例题卡片，点击直接解题

---

**Agent 工作方式**

Math Agent 不是普通聊天机器人，它会**主动调用工具**完成解题：

1. **step_decomposer** — 分析题型，拆解解题步骤
2. **formula_lookup** — 查阅所需公式与定理
3. **calculator** — 精确计算（积分、极限、方程、行列式等）

每次解题你可以展开「工具调用详情」看到完整推导过程。

---

**学习功能**

- 📚 **知识点标签**：点击某个知识点，AI 详细讲解定义和推导
- 🧪 **同类练习题**：每次解题后生成一道练习，点击直接做
- 📌 **错题本**：点「存入错题本」，随时从侧边栏重做
- 🧭 **引导模式**：开启后 AI 用苏格拉底式提问引导你自己想，不直接给答案

---

**模型选择**

底部工具栏可切换模型：
- `deepseek-chat` — 默认，文字解题最稳定
- `Qwen3-VL-*` — 视觉能力强，拍题效果好（SiliconFlow）

---

**小技巧**

- 发完消息后可继续追问，AI 记住上下文
- 闲聊也可以，不一定要发数学题
- 拍题时建议补充文字说明具体问哪部分
""")

    st.divider()
    with st.expander("🎓 课程入口", expanded=True):
        _all_courses = [
            ("大一", ["数学分析", "高等代数", "解析几何"]),
            ("大二", ["常微分方程", "复变函数", "抽象代数", "概率论"]),
            ("大三", ["实变函数", "泛函分析", "点集拓扑", "微分几何", "数值分析", "偏微分方程", "数学建模"]),
        ]
        _btn_idx = 0
        for _grade, _courses in _all_courses:
            st.caption(_grade)
            _ca, _cb = st.columns(2)
            for _ci, _course in enumerate(_courses):
                with (_ca if _ci % 2 == 0 else _cb):
                    _active = st.session_state.get("current_course") == _course
                    if st.button(
                        f"**{_course}**" if _active else _course,
                        key=f"course_{_btn_idx}",
                        use_container_width=True,
                        type="primary" if _active else "secondary",
                    ):
                        st.session_state["current_course"] = _course
                        st.session_state.messages = []
                        st.session_state.pop("prefill", None)
                        st.rerun()
                _btn_idx += 1


# selected_model 从工具栏取（见下方 toolbar），先给默认值
selected_model = st.session_state.get("_sel_model", "deepseek-chat")
_ADMIN_EMAIL = "a13989358483@gmail.com"
use_local = False

# ── 课程横幅（进入课程后始终显示在顶部）──────────────────────────────────────
_cur_course = st.session_state.get("current_course", "")
if _cur_course and _cur_course in _COURSE_TOPICS:
    _cb_left, _cb_right = st.columns([5, 1])
    with _cb_left:
        st.markdown(
            f'<div class="course-banner">📖 {_cur_course}</div>',
            unsafe_allow_html=True,
        )
    with _cb_right:
        if st.button("退出课程", key="exit_course", use_container_width=True):
            st.session_state.pop("current_course", None)
            st.session_state.messages = []
            st.rerun()

# ── 欢迎页（无对话时）────────────────────────────────────────────────────────
if not st.session_state.messages:
    if _cur_course and _cur_course in _COURSE_TOPICS:
        # ── 课程模式：显示知识点选择 ──
        st.markdown(
            f'<div class="greeting-wrap">'
            f'<div class="greeting-sub">选择一个知识点，AI 将从定义、定理到例题系统讲解</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        _topics = _COURSE_TOPICS[_cur_course]
        _tcols = st.columns(2, gap="small")
        for _ti, _topic in enumerate(_topics):
            with _tcols[_ti % 2]:
                if st.button(_topic, key=f"topic_{_ti}", use_container_width=True):
                    _track_topic(_uemail, _cur_course, _topic)
                    st.session_state.pop("user_profile", None)
                    st.session_state["_direct_input"] = (
                        f"【知识点讲解】{_cur_course} · {_topic}"
                    )

    else:
        # ── 默认模式：示例题 ──
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
    else:
        _asst_turn += 1
        st.markdown(f'<span class="turn-badge">第 {_asst_turn} 轮</span>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="asst-bubble-marker" id="abm-{i}"></div>',
                    unsafe_allow_html=True)
        st.markdown(fix_latex(msg["content"]))
        if msg.get("tags"):
            _tcols = st.columns(len(msg["tags"]))
            for _ti, _tag in enumerate(msg["tags"]):
                with _tcols[_ti]:
                    if st.button(_tag, key=f"tag_{i}_{_ti}", use_container_width=True):
                        st.session_state["_direct_input"] = f"请详细讲解「{_tag}」：定义、推导过程和典型例题"
        if msg.get("practice"):
            st.markdown(
                '<p style="font-size:0.8rem;color:#888;margin:6px 0 2px">🧪 同类练习题</p>',
                unsafe_allow_html=True,
            )
            if st.button(msg["practice"], key=f"practice_{i}", use_container_width=True):
                st.session_state["_direct_input"] = msg["practice"]
                st.rerun()
        for _img in msg.get("images", []):
            _cap = _img.get("caption", "")
            st.markdown(
                f'<div style="margin:8px 0">'
                f'<img src="data:image/png;base64,{_img["b64"]}" '
                f'style="width:100%;border-radius:6px;border:1px solid #DDD;" />'
                + (f'<p style="text-align:center;font-size:0.78rem;color:#888;margin:4px 0">{_cap}</p>' if _cap else '')
                + '</div>',
                unsafe_allow_html=True,
            )
        if msg.get("trace"):
            with st.expander("工具调用详情", expanded=False):
                st.code(msg["trace"], language="text")
        # ── 存入错题本按钮 ──
        _prev_msg = next((m for m in reversed(st.session_state.messages[:i])
                          if m["role"] == "user"), None)
        _prev_q = _prev_msg["content"] if _prev_msg else ""
        if _prev_q and not any(w["question"] == _prev_q for w in st.session_state.wrong_book):
            if st.button("📌 存入错题本", key=f"wb_add_{i}", use_container_width=False):
                st.session_state.wrong_book.append({
                    "question": _prev_q,
                    "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "image_b64": _prev_msg.get("image_b64", "") if _prev_msg else "",
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

# ── 麦克风面板（录完即识别，自动发送）──────────────────────────────────────
if st.session_state.get("show_mic"):
    _av = st.audio_input("🎙️ 说出数学题（支持中英文）", key="mic_input",
                         label_visibility="visible")
    if _av:
        with st.spinner("识别中…"):
            _vt, _vt_err = transcribe_audio(_av)
        st.session_state.show_mic = False
        if _vt:
            st.session_state["_direct_input"] = _vt
        else:
            st.error(f"语音识别失败：{_vt_err}" if _vt_err else "未识别到内容，请重试（录音超过1秒）")
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

        # AI 回答
        with st.container():
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
                # 注入学习上下文（仅在对话开始时，且用户有学习记录）
                _profile_ctx = st.session_state.get("user_profile", {})
                _weak_ctx = _profile_ctx.get("weak", [])
                if not history and _weak_ctx:
                    _weak_str = "、".join(
                        f"{w['topic']}（学了{w['visit_count']}次）" for w in _weak_ctx[:4]
                    )
                    solve_history = [{
                        "role": "user",
                        "content": f"[系统提示：该用户的薄弱知识点为：{_weak_str}。讲解时适当关联这些薄弱点，帮助巩固。]"
                    }, {
                        "role": "assistant",
                        "content": "好的，我已了解你的学习情况，会在讲解时适当关联薄弱点。"
                    }]
                else:
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
                _solve_local = False
                _use_guide = guide_mode and not _img_bytes and not _sim_data
                if _img_bytes:
                    if _secret("SILICONFLOW_API_KEY"):
                        _solve_model = "Qwen/Qwen3-VL-30B-A3B-Instruct"
                        status.update(label="切换视觉模型（Qwen VL）…")
                    else:
                        # 没有视觉 API，先 OCR 成文字再解题
                        status.update(label="识别图片内容…")
                        _ocr = ocr_math_image(_img_bytes)
                        if _ocr and not _ocr.startswith("（"):
                            solve_input = f"请解答以下题目：{_ocr}"
                            if user_input and user_input != "请解答图片中的数学题":
                                solve_input += f"\n（补充说明：{user_input}）"
                        _img_bytes = None  # 已转为文字，不再发图
                _agent = get_agent(_solve_local, _solve_model, guide_mode=_use_guide)

                buf = StringIO()
                try:
                    with contextlib.redirect_stdout(buf):
                        stream = _agent.solve_stream(
                            solve_input, history=solve_history,
                            on_tool_call=on_tool_call, image_bytes=_img_bytes,
                        )
                    err = None
                except Exception as exc:
                    import traceback
                    stream, err = None, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
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
                        _ntcols = st.columns(len(tags))
                        for _nti, _ntag in enumerate(tags):
                            with _ntcols[_nti]:
                                if st.button(_ntag, key=f"tag_new_{_nti}", use_container_width=True):
                                    st.session_state["_direct_input"] = f"请详细讲解「{_ntag}」：定义、推导过程和典型例题"
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
            # 取走工具生成的图像并展示
            _new_images = get_and_clear_pending_images()
            for _img in _new_images:
                _cap = _img.get("caption", "")
                st.markdown(
                    f'<div style="margin:8px 0">'
                    f'<img src="data:image/png;base64,{_img["b64"]}" '
                    f'style="width:100%;border-radius:6px;border:1px solid #DDD;" />'
                    + (f'<p style="text-align:center;font-size:0.78rem;color:#888;margin:4px 0">{_cap}</p>' if _cap else '')
                    + '</div>',
                    unsafe_allow_html=True,
                )
            if trace:
                with st.expander("工具调用详情", expanded=False):
                    st.code(trace, language="text")

    st.session_state.messages.append({
        "role": "assistant", "content": answer, "tags": tags, "trace": trace,
        "practice": practice, "images": _new_images if stream is not None else [],
    })
    st.rerun()  # 刷新让欢迎页消失、聊天历史正确显示
