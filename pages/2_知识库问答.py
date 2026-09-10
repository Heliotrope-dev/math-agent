"""知识库问答页 — RAG 语义检索 + 千问生成。"""

import logging
import os

import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

for _k in ("QWEN_API_KEY", "SILICONFLOW_API_KEY"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from components.config import get_secret
from components.ui_helpers import _BASE_CSS
from components.rag_engine import RAGEngine
from components.rag_ingest import chunk_documents, parse_pdf, parse_txt
from components.auth import check_and_bump_usage

st.markdown(_BASE_CSS, unsafe_allow_html=True)

if not st.session_state.get("logged_in", False):
    st.warning("请先登录后使用")
    st.page_link("_math_page.py", label="← 返回登录", use_container_width=False)
    st.stop()

# 知识库按用户隔离，user_email 为空说明登录态异常，不能退化成共享桶
_user = st.session_state.get("user_email", "")
if not _user:
    st.error("登录状态异常，请重新登录后再使用知识库。")
    st.page_link("_math_page.py", label="← 返回登录", use_container_width=False)
    st.stop()


@st.cache_resource
def get_engine() -> RAGEngine:
    return RAGEngine()


def _esc_html(s: str) -> str:
    """转义后再塞进 unsafe_allow_html 的片段——上传的文档内容/用户输入都不可信，
    之前 c["text"]（RAG 检索出的文档原文片段）没转义就直接渲染，是存储型 XSS。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_ALLOWED_KB_EXTS = (".pdf", ".txt", ".md")


def _ingest_file(engine: RAGEngine, uploaded, user: str) -> int:
    file_bytes = uploaded.getvalue()
    name = uploaded.name
    # st.file_uploader 的 type= 只是前端提示，不是硬限制（拖拽/程序化上传都能绕开）；
    # 之前这里没有二次校验，任何非 .pdf 文件一律走 parse_txt，只要能被
    # utf-8/gb18030/latin-1 三种编码之一解码就会被当成合法文本悄悄收进知识库——
    # 跟"仅支持 PDF/TXT/Markdown"的说明不符，这里补上服务端校验。
    if not name.lower().endswith(_ALLOWED_KB_EXTS):
        raise ValueError(f"不支持的文件类型：{name}（仅支持 PDF / TXT / Markdown）")
    if name.lower().endswith(".pdf"):
        docs = parse_pdf(file_bytes, name)
    else:
        docs = parse_txt(file_bytes, name)
    chunks = chunk_documents(docs, user)
    return engine.add_documents(chunks, name, user)


def render_sidebar(engine: RAGEngine, user: str) -> None:
    with st.sidebar:
        st.page_link("_math_page.py", label="← 数学解题", use_container_width=True)
        st.divider()
        st.subheader("知识库管理")

        missing = [k for k in ("QWEN_API_KEY", "SILICONFLOW_API_KEY") if not get_secret(k)]
        if missing:
            st.error("缺少配置：" + "、".join(missing))

        _uploader_key = f"doc_uploader_{st.session_state.get('_uploader_gen', 0)}"
        uploaded_files = st.file_uploader(
            "上传文档",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            help="支持 PDF / TXT / Markdown，同名文件自动覆盖",
            key=_uploader_key,
        )
        _col_proc, _col_clear = st.columns([3, 1])
        with _col_proc:
            _do_process = uploaded_files and st.button("处理文件", use_container_width=True, type="primary")
        with _col_clear:
            if st.button("清空", use_container_width=True, help="清空已选文件，重新选择"):
                st.session_state["_uploader_gen"] = st.session_state.get("_uploader_gen", 0) + 1
                st.rerun()
        if _do_process:
            progress = st.progress(0.0, text="开始处理…")
            total_chunks, errors = 0, []
            for i, f in enumerate(uploaded_files):
                progress.progress(i / len(uploaded_files), text=f"正在处理 {f.name}…")
                try:
                    total_chunks += _ingest_file(engine, f, user)
                except Exception as e:
                    errors.append(f"{f.name}：{e}")
            progress.progress(1.0, text="处理完成")
            if total_chunks:
                st.success(f"已添加 {total_chunks} 个段落")
            for err in errors:
                st.error(err)
                st.caption("处理失败的文件可以点上面「清空」重新选择再试一次。")

        st.divider()
        st.caption("已上传文档")
        doc_counts = engine.list_documents(user)
        if not doc_counts:
            st.caption("（暂无文档）")
        for source, count in sorted(doc_counts.items()):
            col_name, col_del = st.columns([4, 1])
            col_name.markdown(f"**{source}**  \n{count} 段落")
            if col_del.button("删除", key=f"del::{source}", help=f"删除 {source}"):
                engine.delete_document(source, user)
                st.rerun()


def render_chat(engine: RAGEngine, user: str) -> None:
    st.markdown("""
    <div style="padding:16px 0 8px">
        <div style="font-size:1.6rem;font-weight:600;letter-spacing:-0.01em;margin-bottom:4px">知识库问答</div>
        <div style="font-size:0.83rem;color:var(--text-muted)">上传文档后提问 · 语义检索 + DeepSeek 生成 · 附引用来源</div>
    </div>
    """, unsafe_allow_html=True)

    if engine.user_chunk_count(user) == 0:
        st.info("请先在左侧上传文档")

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    # ── 历史消息（与 math-agent 同款气泡样式）──────────────────────────────────
    for msg in st.session_state.rag_messages:
        if msg["role"] == "user":
            _safe = _esc_html(msg["content"])
            st.markdown(
                f'<div class="msg-row-user"><div class="bubble-user">{_safe}</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="asst-bubble-marker"></div>', unsafe_allow_html=True)
            st.markdown(msg["content"])
            if msg.get("chunks"):
                with st.expander(f"参考来源（{len(msg['chunks'])} 条）"):
                    for i, c in enumerate(msg["chunks"], 1):
                        st.markdown(f"**{i}. {c['source']} · 第{c['page']}页** （相关度 {1 - c['distance']:.0%}）")
                        _snippet = _esc_html(c["text"][:400]) + ("…" if len(c["text"]) > 400 else "")
                        st.markdown(f'<p style="font-size:0.8rem;color:var(--text-muted);line-height:1.6;margin:4px 0 0">{_snippet}</p>', unsafe_allow_html=True)

    # ── 输入框 ─────────────────────────────────────────────────────────────────
    question = st.chat_input("输入你的问题…")
    if not question:
        return

    _safe_q = _esc_html(question)
    st.markdown(
        f'<div class="msg-row-user"><div class="bubble-user">{_safe_q}</div></div>',
        unsafe_allow_html=True,
    )
    st.session_state.rag_messages.append({"role": "user", "content": question})

    st.markdown('<div class="asst-bubble-marker"></div>', unsafe_allow_html=True)
    _quota_ok, _quota_msg = check_and_bump_usage(user)
    if not _quota_ok:
        answer, chunks = _quota_msg, []
    else:
        with st.spinner("检索知识库并生成回答…"):
            try:
                chunks = engine.query(question, user)
                answer = engine.generate_answer(question, chunks, st.session_state.rag_messages[:-1])
            except Exception as e:
                answer = f"出错：{e}"
                chunks = []

    st.markdown(answer)
    if chunks:
        with st.expander(f"参考来源（{len(chunks)} 条）"):
            for i, c in enumerate(chunks, 1):
                st.markdown(f"**{i}. {c['source']} · 第{c['page']}页** （相关度 {1 - c['distance']:.0%}）")
                _snippet = _esc_html(c["text"][:400]) + ("…" if len(c["text"]) > 400 else "")
                st.markdown(f'<p style="font-size:0.8rem;color:var(--text-muted);line-height:1.6;margin:4px 0 0">{_snippet}</p>', unsafe_allow_html=True)

    st.session_state.rag_messages.append(
        {"role": "assistant", "content": answer, "chunks": chunks}
    )
    st.rerun()


engine = get_engine()
render_sidebar(engine, _user)
render_chat(engine, _user)
