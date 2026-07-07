import random
import base64
import streamlit as st
import streamlit.components.v1 as _cv1

from components.auth import (
    _invalidate_token,
    _load_user_profile,
    _save_wrong_book,
)

_ALL_COURSES = [
    ("大一", ["数学分析", "高等代数", "解析几何"]),
    ("大二", ["常微分方程", "复变函数", "抽象代数", "概率论"]),
    ("大三", ["实变函数", "泛函分析", "点集拓扑", "微分几何", "数值分析", "偏微分方程", "数学建模"]),
]


def render_sidebar() -> None:
    """侧边栏全部内容：在 app.py 的 `with st.sidebar:` 块内调用。"""
    _uemail = st.session_state.get("user_email", "")

    # ── 用户信息 + 退出 ──────────────────────────────────────────────────────
    st.markdown(
        f'<p class="sb-email" style="font-size:0.75rem;color:#888;margin:10px 0 10px">{_uemail}</p>',
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

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.page_link("pages/2_📚_知识库问答.py", label="知识库问答", use_container_width=True)
    st.divider()

    # ── 最近问题（最多显示20条）─────────────────────────────────────────────
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

    # ── 错题本 ────────────────────────────────────────────────────────────────
    wrong_book = st.session_state.wrong_book
    with st.expander(f"错题本（{len(wrong_book)}）", expanded=False):
        if not wrong_book:
            st.caption("解完题后点「存入错题本」")
        else:
            if st.button("🎲 随机复习一题", key="wb_review", use_container_width=True,
                         type="primary"):
                _rw = random.choice(wrong_book)
                _rw_img = _rw.get("image_b64", "")
                if _rw_img:
                    st.session_state["pending_attachment"] = {
                        "type": "image",
                        "bytes": base64.b64decode(_rw_img),
                        "name": "错题图片",
                    }
                    _rw_txt = _rw["question"].lstrip("📷").strip()
                    if _rw_txt and _rw_txt != "图片题目":
                        st.session_state["prefill"] = _rw_txt
                else:
                    st.session_state["_direct_input"] = (
                        f"【错题复习】请重新完整解答这道我之前做错的题：{_rw['question']}"
                    )
                st.rerun()
            for wi, wp in enumerate(wrong_book):
                q_preview = wp["question"][:48] + ("…" if len(wp["question"]) > 48 else "")
                st.markdown(f"**{wi+1}.** {q_preview}")
                st.caption(wp.get("saved_at", ""))
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("重做", key=f"wb_redo_{wi}", use_container_width=True):
                        _wb_img = wp.get("image_b64", "")
                        if _wb_img:
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

    # ── 学习档案 ──────────────────────────────────────────────────────────────
    if "user_profile" not in st.session_state:
        st.session_state["user_profile"] = _load_user_profile(_uemail)
    _profile = st.session_state.get("user_profile", {})
    if _profile:
        with st.expander("学习档案", expanded=False):
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

    # ── 清空对话 ──────────────────────────────────────────────────────────────
    if st.button("清空对话", use_container_width=True):
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

    # ── 使用手册 ──────────────────────────────────────────────────────────────
    with st.expander("使用手册", expanded=False):
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

    # ── 课程入口 ──────────────────────────────────────────────────────────────
    with st.expander("课程入口", expanded=True):
        _btn_idx = 0
        for _grade, _courses in _ALL_COURSES:
            st.caption(_grade)
            for _course in _courses:
                _active = st.session_state.get("current_course") == _course
                if st.button(
                    _course,
                    key=f"course_{_btn_idx}",
                    use_container_width=True,
                    type="primary" if _active else "secondary",
                ):
                    st.session_state["current_course"] = _course
                    st.session_state.messages = []
                    st.session_state.pop("prefill", None)
                    st.rerun()
                _btn_idx += 1
