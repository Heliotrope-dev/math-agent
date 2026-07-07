"""知识库问答页 — RAG 语义检索 + DeepSeek 生成。"""

import logging
import os

import streamlit as st

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

st.set_page_config(page_title="知识库问答", page_icon="📚", layout="wide")

for _k in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY"):
    if _k not in os.environ:
        try:
            os.environ[_k] = st.secrets[_k]
        except Exception:
            pass

from components.config import get_secret
from components.ui_helpers import _BASE_CSS, _DARK_CSS
from components.rag_engine import RAGEngine
from components.rag_ingest import chunk_documents, parse_pdf, parse_txt

# 复用 math-agent 的主题 CSS，隐藏原生导航
_dm = st.session_state.get("dark_mode", False)
st.markdown(_BASE_CSS + (_DARK_CSS if _dm else ""), unsafe_allow_html=True)

# 权限检查
if not st.session_state.get("logged_in", False):
    st.warning("请先登录后使用")
    st.page_link("app.py", label="← 返回登录", use_container_width=False)
    st.stop()


@st.cache_resource
def get_engine() -> RAGEngine:
    return RAGEngine()


def _ingest_file(engine: RAGEngine, uploaded) -> int:
    file_bytes = uploaded.getvalue()
    name = uploaded.name
    if name.lower().endswith(".pdf"):
        docs = parse_pdf(file_bytes, name)
    else:
        docs = parse_txt(file_bytes, name)
    chunks = chunk_documents(docs)
    return engine.add_documents(chunks, name)


def render_sidebar(engine: RAGEngine) -> None:
    with st.sidebar:
        st.page_link("app.py", label="← 数学解题", use_container_width=True)
        st.divider()
        st.title("📚 知识库")

        missing = [k for k in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY") if not get_secret(k)]
        if missing:
            st.error("缺少配置：" + "、".join(missing))

        uploaded_files = st.file_uploader(
            "上传文档",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            help="支持 PDF / TXT / Markdown，同名文件自动覆盖",
        )
        if uploaded_files and st.button("处理文件", use_container_width=True, type="primary"):
            progress = st.progress(0.0, text="开始处理…")
            total_chunks, errors = 0, []
            for i, f in enumerate(uploaded_files):
                progress.progress(i / len(uploaded_files), text=f"正在处理 {f.name}…")
                try:
                    total_chunks += _ingest_file(engine, f)
                except Exception as e:
                    errors.append(f"{f.name}：{e}")
            progress.progress(1.0, text="处理完成")
            if total_chunks:
                st.success(f"已添加 {total_chunks} 个段落")
            for err in errors:
                st.error(err)

        st.divider()
        st.subheader("已上传文档")
        doc_counts = engine.list_documents()
        if not doc_counts:
            st.caption("（暂无文档）")
        for source, count in sorted(doc_counts.items()):
            col_name, col_del = st.columns([4, 1])
            col_name.markdown(f"**{source}**\n\n{count} 个段落")
            if col_del.button("🗑", key=f"del::{source}", help=f"删除 {source}"):
                engine.delete_document(source)
                st.rerun()


def render_chat(engine: RAGEngine) -> None:
    st.title("📚 知识库问答")
    st.caption("上传文档后提问 · 语义检索 + DeepSeek 生成 · 答案附引用来源")

    if engine.collection.count() == 0:
        st.info("👆 请先在左侧上传文档")

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("chunks"):
                with st.expander(f"📎 参考来源（{len(msg['chunks'])} 条）"):
                    for i, c in enumerate(msg["chunks"], 1):
                        st.markdown(f"**{i}. {c['source']} · 第{c['page']}页** （距离 {c['distance']}）")
                        st.text(c["text"][:500] + ("…" if len(c["text"]) > 500 else ""))

    question = st.chat_input("输入你的问题…")
    if not question:
        return

    st.session_state.rag_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("检索知识库…"):
                chunks = engine.query(question)
            with st.spinner("生成回答…"):
                answer = engine.generate_answer(question, chunks, st.session_state.rag_messages[:-1])
        except Exception as e:
            answer = f"⚠️ {e}"
            chunks = []
        st.markdown(answer)
        if chunks:
            with st.expander(f"📎 参考来源（{len(chunks)} 条）"):
                for i, c in enumerate(chunks, 1):
                    st.markdown(f"**{i}. {c['source']} · 第{c['page']}页** （距离 {c['distance']}）")
                    st.text(c["text"][:500] + ("…" if len(c["text"]) > 500 else ""))

    st.session_state.rag_messages.append(
        {"role": "assistant", "content": answer, "chunks": chunks}
    )


engine = get_engine()
render_sidebar(engine)
render_chat(engine)
