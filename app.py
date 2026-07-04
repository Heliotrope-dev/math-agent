"""
app.py — Math Solver Web UI

Launch:
  streamlit run app.py
  USE_LOCAL=1 streamlit run app.py
"""

import os, sys, base64, requests, re, time, random, json, contextlib, logging
from io import StringIO, BytesIO
from datetime import datetime
import tempfile

from PIL import Image
import streamlit as st

# 默认日志级别是 WARNING，INFO/DEBUG 全被过滤；显式配置一次（重复调用无副作用）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

for _k in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY",
           "OLLAMA_BASE_URL", "SUPABASE_URL", "SUPABASE_KEY"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from agent import MathAgent, CLOUD_PROVIDERS, route_model
from tools import get_and_clear_pending_images, compress_image
from components.auth import (
    _track_topic,
    _hash_pw, _check_pw, _user_exists, _check_user,
    _register_user, _create_token, _validate_token,
    _load_wrong_book, _save_wrong_book,
)
from components.ui_helpers import _BASE_CSS, _DARK_CSS
from components.config import get_secret, DEFAULT_MODEL, ADMIN_EMAIL, OCR_MODEL
from components.sidebar import render_sidebar

def _show_login_page():
    st.markdown("""
    <div class="login-logo">
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

# ── 启动环境校验：至少配置一个云端 API Key，否则友好提示而非运行时崩溃 ────────
if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("SILICONFLOW_API_KEY")):
    st.error(
        "⚠️ 未检测到可用的模型 API Key。\n\n"
        "请配置环境变量（或 Streamlit Secrets）中的 **DEEPSEEK_API_KEY** "
        "或 **SILICONFLOW_API_KEY** 至少一个，然后刷新页面。"
    )
    st.stop()

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

# ── 手机端 CSS 强制注入父页面 head（绕过 Streamlit 组件 CSS 作用域）──────────
_cv1.html("""
<script>
(function() {
try {
    var doc = window.parent.document;
    if (doc.getElementById('_mobile_css')) return;
    var s = doc.createElement('style');
    s.id = '_mobile_css';
    s.textContent =
        '[data-testid="stSidebarCollapseButton"]{display:none!important}' +
        '[data-testid="collapsedControl"]{display:none!important}' +
        'button[data-testid="stBaseButton-headerNoPadding"]{display:none!important}' +
        '@media(max-width:768px){' +
            /* 主内容顶部留白，防止汉堡按钮遮住内容 */
            '[data-testid="stAppViewContainer"],[data-testid="stMain"]{padding-top:56px!important}' +
            '.block-container{padding-top:8px!important}' +
            /* 侧边栏顶部留给汉堡按钮，内边距紧凑 */
            '[data-testid="stSidebar"]{padding-top:56px!important}' +
            '[data-testid="stSidebar"]>div:first-child{padding:0 10px 12px!important}' +
            /* 侧边栏各区块间距压缩 */
            '[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:4px!important}' +
            '[data-testid="stSidebar"] [data-testid="element-container"]{margin-bottom:0!important}' +
            /* 邮件不截断 */
            '[data-testid="stSidebar"] p{' +
                'font-size:0.78rem!important;overflow:hidden!important;' +
                'text-overflow:ellipsis!important;white-space:nowrap!important;' +
                'margin:0 0 6px!important}' +
            /* 按钮紧凑 */
            '[data-testid="stSidebar"] .stButton>button{' +
                'min-height:34px!important;height:34px!important;' +
                'font-size:0.82rem!important;padding:0 10px!important;' +
                'border-radius:8px!important;margin:0!important}' +
            /* expander header */
            '[data-testid="stSidebar"] details summary,' +
            '[data-testid="stSidebar"] [data-testid="stExpander"] summary{' +
                'font-size:0.82rem!important;padding:6px 10px!important;min-height:34px!important}' +
            '[data-testid="stSidebar"] [data-testid="stExpander"]{margin:0 0 4px!important}' +
            /* 课程 pills 在侧边栏显示正常 */
            '[data-testid="stSidebar"] [data-testid="stPills"] button{font-size:0.72rem!important;padding:2px 8px!important}' +
        '}';
    doc.head.appendChild(s);
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

st.markdown(_BASE_CSS, unsafe_allow_html=True)

# ── 登录检查（未登录则显示登录页并阻止后续渲染）─────────────────────────────
if not st.session_state.get("logged_in"):
    _show_login_page()
    st.stop()

# ── 配置 ──────────────────────────────────────────────────────────────────────
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

def ocr_math_image(image_bytes):
    """拍题 OCR：用 SiliconFlow Qwen-VL 识别图片中的数学题文字。"""
    key = get_secret("SILICONFLOW_API_KEY")
    if not key:
        return "（未配置 SILICONFLOW_API_KEY，无法识别图片）"
    try:
        from agent import MathAgent
        agent = MathAgent(use_local=False, model=OCR_MODEL)
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
    sf_key = get_secret("SILICONFLOW_API_KEY")
    if not sf_key:
        return "", "未配置 SILICONFLOW_API_KEY，请在 .streamlit/secrets.toml 添加"

    raw = audio_file.read()
    if len(raw) < 1000:
        return "", "录音太短，请说话后再松开（至少1秒）"

    # 优先用 UploadedFile 自带的 MIME type，避免 magic bytes 猜错
    browser_mime = getattr(audio_file, "type", "") or ""
    if browser_mime and "/" in browser_mime:
        mime = browser_mime
        raw_ext = browser_mime.split("/")[-1].split(";")[0]  # 去掉 codec 参数
        ext = {"mpeg": "mp3", "ogg": "ogg", "mp4": "m4a", "x-m4a": "m4a"}.get(raw_ext, raw_ext)
    elif raw[:4] == b"RIFF":
        mime, ext = "audio/wav", "wav"
    elif raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
        mime, ext = "audio/mpeg", "mp3"
    elif len(raw) > 8 and raw[4:8] == b"ftyp":
        mime, ext = "audio/mp4", "m4a"
    elif raw[:4] == b"OggS":
        mime, ext = "audio/ogg", "ogg"
    elif raw[:4] == b"\x1a\x45\xdf\xa3":
        mime, ext = "audio/webm", "webm"
    else:
        mime, ext = "audio/webm", "webm"

    try:
        resp = requests.post(
            "https://api.siliconflow.cn/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {sf_key}"},
            files={"file": (f"recording.{ext}", raw, mime)},
            data={"model": "FunAudioLLM/SenseVoiceSmall"},
            timeout=30,
        )
        if not resp.ok:
            return "", f"API 错误 {resp.status_code}：{resp.text[:200]}"
        data = resp.json()
        if "error" in data:
            return "", f"识别失败：{data['error']}"
        text = data.get("text", "").strip()
        if not text:
            return "", f"未识别到语音（格式:{ext}，大小:{len(raw)}B），请靠近麦克风或说长一点"
        return text, ""
    except requests.Timeout:
        return "", "识别超时（30s），请检查网络后重试"
    except Exception as e:
        return "", f"识别出错：{e}"

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
    st.markdown(_DARK_CSS, unsafe_allow_html=True)

# 始终注入：暗色时写入覆盖样式+MutationObserver，日间时清除
_dm_js_flag = "true" if st.session_state.dark_mode else "false"
_cv1.html(f"""<script>
(function(){{
try{{
    var dark = {_dm_js_flag};
    var doc  = window.parent.document;
    var SID  = '_dm_override_css';
    var el   = doc.getElementById(SID);
    if (!dark) {{ if (el) el.remove(); return; }}
    var s = el || doc.createElement('style');
    if (!el) {{ s.id = SID; doc.head.appendChild(s); }}
    var CSS =
        ':root{{--background-color:#0D0D14!important;--secondary-background-color:#16162A!important;--text-color:#DEE1F5!important}}' +
        'body,html,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{{background:#0D0D14!important}}' +
        '[data-testid="stBottom"],[data-testid="stBottomBlockContainer"]{{background:#0D0D14!important}}' +
        '[data-testid="stBottom"]>div,[data-testid="stBottom"]>div>div{{background:#0D0D14!important}}' +
        '[data-testid="stHorizontalBlock"]:has(.toolbar-btn){{background:#0D0D14!important}}' +
        '[data-testid="stChatInputContainer"]{{background:#16162A!important;border:1.5px solid #282845!important;border-radius:24px!important;box-shadow:none!important}}' +
        '[data-testid="stChatInputContainer"]>div,[data-testid="stChatInputContainer"]>div>div{{background:#16162A!important}}' +
        '[data-testid="stChatInput"]{{background:#16162A!important}}' +
        '[data-testid="stChatInputTextArea"]{{background:transparent!important;border:none!important;box-shadow:none!important;color:#DEE1F5!important}}' +
        '[data-testid="stChatInputTextArea"]::placeholder{{color:#6B6B95!important}}' +
        '[data-testid="stChatInputSubmitButton"] button{{background:#5B8CFF!important}}';
    function applyInline() {{
        var inp = doc.querySelector('[data-testid="stChatInputContainer"]');
        if (inp) {{
            inp.style.setProperty('background','#16162A','important');
            inp.style.setProperty('border','1.5px solid #282845','important');
            inp.style.setProperty('border-radius','24px','important');
            inp.style.setProperty('box-shadow','none','important');
            inp.querySelectorAll('*').forEach(function(el) {{
                var tag = el.tagName.toLowerCase();
                if (tag==='textarea'||tag==='input') {{
                    el.style.setProperty('color','#DEE1F5','important');
                    el.style.setProperty('background','transparent','important');
                    el.style.setProperty('-webkit-text-fill-color','#DEE1F5','important');
                    el.style.setProperty('caret-color','#DEE1F5','important');
                }} else if (tag!=='button'&&tag!=='svg'&&tag!=='path') {{
                    el.style.setProperty('background','#16162A','important');
                }}
            }});
        }}
        var bot = doc.querySelector('[data-testid="stBottom"]');
        if (bot) bot.style.setProperty('background','#0D0D14','important');
    }}
    function apply() {{ s.textContent = CSS; applyInline(); }}
    apply();
    if (!doc._dmObs) {{
        doc._dmObs = new MutationObserver(function() {{
            clearTimeout(doc._dmObs._t);
            doc._dmObs._t = setTimeout(apply, 120);
        }});
        doc._dmObs.observe(doc.body, {{childList:true, subtree:true}});
    }}
}} catch(e) {{}}
}})();
</script>""", height=1)


# ── 侧边栏 ────────────────────────────────────────────────────────────────────
with st.sidebar:
    render_sidebar()


# selected_model 从工具栏取（见下方 toolbar），先给默认值
selected_model = st.session_state.get("_sel_model", DEFAULT_MODEL)
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

# ── 麦克风面板（录完直接识别发送）───────────────────────────────────────────
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
        _thumb_b64 = base64.b64encode(compress_image(_patt["bytes"], max_size=80)).decode()
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

# ── 底部工具栏 ───────────────────────────────────────────────────────────────
guide_mode = st.session_state.guide_mode

_MODEL_LABELS = {
    "deepseek-chat":                   "DeepSeek",
    "Qwen/Qwen3-VL-30B-A3B-Instruct":  "Qwen3-VL 30B",
    "Qwen/Qwen3-VL-32B-Instruct":      "Qwen3-VL 32B",
    "Qwen/Qwen3-VL-32B-Thinking":      "Qwen3 思维链",
    "Qwen/Qwen3-VL-8B-Instruct":       "Qwen3-VL 8B",
}
_copts     = list(CLOUD_PROVIDERS.keys())
_clabels   = [_MODEL_LABELS.get(m, m) for m in _copts]
_def_idx   = _copts.index("deepseek-chat")

try:
    _tb_mic, _tb_model, _tb_plus = st.columns([1, 6, 1], gap="small", vertical_alignment="center")
except TypeError:
    _tb_mic, _tb_model, _tb_plus = st.columns([1, 6, 1], gap="small")

with _tb_mic:
    st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
    _mic_active = st.session_state.get("show_mic")
    if st.button("✕" if _mic_active else "🎙️", key="tb_mic", help="语音输入"):
        if _mic_active:
            st.session_state.show_mic = False
        else:
            st.session_state.show_mic = True
        st.session_state.show_plus = False
        st.session_state.show_photo = False
        st.session_state.show_file = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with _tb_model:
    st.markdown('<div class="toolbar-model">', unsafe_allow_html=True)
    _sel_label = st.selectbox(
        "模型", _clabels, index=_def_idx,
        label_visibility="collapsed", key="tb_model_cloud",
    )
    selected_model = _copts[_clabels.index(_sel_label)]
    st.session_state["_sel_model"] = selected_model
    st.markdown('</div>', unsafe_allow_html=True)

with _tb_plus:
    st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
    if st.button("✕" if st.session_state.get("show_plus") else "➕", key="tb_plus", help="附件 / 拍题"):
        st.session_state.show_plus = not st.session_state.get("show_plus", False)
        st.session_state.show_mic = False
        st.session_state.show_photo = False
        st.session_state.show_file = False
        st.session_state["_panel_just_toggled"] = True
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
_img_b64_bubble = None

if _submitted:
    if _similar_ctx:
        user_input = "🎯 举一反三"
        display_text = "🎯 举一反三"
    elif _patt_send:
        att = _patt_send
        if att["type"] == "image":
            _img_bytes = att["bytes"]
            _img_b64_bubble = base64.b64encode(compress_image(_img_bytes, max_size=400)).decode()
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
    if _img_bytes and "_img_b64_bubble" in locals():
        _msg_record["image_b64"] = _img_b64_bubble
    st.session_state.messages.append(_msg_record)

    with _new_turn:
        # 用户气泡
        _safe_disp = (display_text or user_input).replace("<", "&lt;").replace(">", "&gt;")
        _new_img_html = ""
        if _img_bytes and "_img_b64_bubble" in locals():
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
                        status.update(label=f"正在调用 {label}…")
                        trace_lines.append(f"[{ts}] {label}\n   参数: {args}")
                    else:
                        elapsed = time.time() - _tool_start.get(name, time.time())
                        status.update(label=f"✓ {label} 完成（{elapsed:.1f}s）")
                        preview = str(result)[:120] + ("…" if len(str(result)) > 120 else "")
                        trace_lines.append(f"   → {preview}  ({elapsed:.1f}s)\n")

                _solve_model = selected_model
                _solve_local = False
                _use_guide = guide_mode and not _img_bytes and not _sim_data
                if _img_bytes and not get_secret("SILICONFLOW_API_KEY"):
                    # 没有视觉 API，先 OCR 成文字再解题
                    status.update(label="识别图片内容…")
                    _ocr = ocr_math_image(_img_bytes)
                    if _ocr and not _ocr.startswith("（"):
                        solve_input = f"请解答以下题目：{_ocr}"
                        if user_input and user_input != "请解答图片中的数学题":
                            solve_input += f"\n（补充说明：{user_input}）"
                    _img_bytes = None  # 已转为文字，不再发图
                # 智能路由：有图 → 视觉模型；短闲聊 → 轻量模型
                # 仅在用户处于默认模型（或必须切视觉）时生效，不覆盖用户的显式选择
                if _img_bytes or selected_model == "deepseek-chat":
                    _routed = route_model(solve_input, image_bytes=_img_bytes,
                                          default=selected_model)
                    if _routed != _solve_model:
                        _solve_model = _routed
                        status.update(label="切换视觉模型（Qwen VL）…" if _img_bytes
                                      else "简单问题，切换轻量模型…")
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
