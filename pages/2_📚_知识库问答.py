"""知识库问答页 — RAG 语义检索 + DeepSeek 生成。"""

import logging
import os

import streamlit as st
import streamlit.components.v1 as _cv1

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

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

_dm = st.session_state.get("dark_mode", False)
st.markdown(_BASE_CSS + (_DARK_CSS if _dm else ""), unsafe_allow_html=True)

_dm_flag = "true" if _dm else "false"
_cv1.html(f"""<script>
(function(){{
try{{
    var dark = {_dm_flag};
    var doc = window.parent.document;
    var SID = '_dm_rag_css';
    var el = doc.getElementById(SID);
    if (!dark) {{ if (el) el.remove(); return; }}
    var s = el || doc.createElement('style');
    if (!el) {{ s.id = SID; doc.head.appendChild(s); }}
    s.textContent =
        '[data-testid="stChatInput"]{{background:#16162A!important;border:1.5px solid #282845!important;border-radius:24px!important;box-shadow:none!important}}' +
        '[data-testid="stChatInput"]>div,[data-testid="stChatInput"]>div>div{{background:#16162A!important}}' +
        '[data-testid="stChatInputTextArea"]{{background:#16162A!important;color:#DEE1F5!important;-webkit-text-fill-color:#DEE1F5!important;caret-color:#DEE1F5!important;border:none!important}}' +
        '[data-testid="stChatInputTextArea"]::placeholder{{color:#6B6B95!important}}' +
        '[data-testid="stChatInputSubmitButton"] button{{background:#5B8CFF!important}}' +
        '[data-testid="stBottom"],[data-testid="stBottomBlockContainer"]{{background:#0D0D14!important}}' +
        '[data-testid="stBottom"]>div,[data-testid="stBottom"]>div>div{{background:#0D0D14!important}}';
    function applyInline() {{
        var inp = doc.querySelector('[data-testid="stChatInput"]');
        if (inp) {{
            inp.style.setProperty('background','#16162A','important');
            inp.style.setProperty('border','1.5px solid #282845','important');
            inp.style.setProperty('border-radius','24px','important');
            inp.querySelectorAll('*').forEach(function(d){{ d.style.setProperty('background','#16162A','important'); }});
            inp.querySelectorAll('textarea,input').forEach(function(t){{
                t.style.setProperty('color','#DEE1F5','important');
                t.style.setProperty('background','#16162A','important');
                t.style.setProperty('-webkit-text-fill-color','#DEE1F5','important');
                t.style.setProperty('caret-color','#DEE1F5','important');
            }});
        }}
        doc.querySelectorAll('[data-testid="stBottom"],[data-testid="stBottomBlockContainer"]').forEach(function(bt){{
            bt.style.setProperty('background','#0D0D14','important');
            bt.querySelectorAll('*').forEach(function(e2){{ e2.style.setProperty('background','#0D0D14','important'); }});
        }});
    }}
    applyInline();
    if (!doc._dmRagObs) {{
        doc._dmRagObs = new MutationObserver(function(muts){{
            if (!muts.some(function(m){{ return m.addedNodes.length>0; }})) return;
            clearTimeout(doc._dmRagObs._t);
            doc._dmRagObs._t = setTimeout(applyInline, 30);
        }});
        doc._dmRagObs.observe(doc.body, {{childList:true,subtree:true}});
    }}
}} catch(e) {{}}
}})();
</script>""", height=1)

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
        st.subheader("知识库管理")

        missing = [k for k in ("DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY") if not get_secret(k)]
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
                    total_chunks += _ingest_file(engine, f)
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
        doc_counts = engine.list_documents()
        if not doc_counts:
            st.caption("（暂无文档）")
        for source, count in sorted(doc_counts.items()):
            col_name, col_del = st.columns([4, 1])
            col_name.markdown(f"**{source}**  \n{count} 段落")
            if col_del.button("删除", key=f"del::{source}", help=f"删除 {source}"):
                engine.delete_document(source)
                st.rerun()


def render_chat(engine: RAGEngine) -> None:
    st.markdown("""
    <div style="padding:16px 0 8px">
        <div style="font-size:1.6rem;font-weight:600;letter-spacing:-0.01em;margin-bottom:4px">知识库问答</div>
        <div style="font-size:0.83rem;color:var(--text-muted)">上传文档后提问 · 语义检索 + DeepSeek 生成 · 附引用来源</div>
    </div>
    """, unsafe_allow_html=True)

    if engine.collection.count() == 0:
        st.info("请先在左侧上传文档")

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    # ── 历史消息（与 math-agent 同款气泡样式）──────────────────────────────────
    for msg in st.session_state.rag_messages:
        if msg["role"] == "user":
            _safe = msg["content"].replace("<", "&lt;").replace(">", "&gt;")
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
                        st.markdown(f'<p style="font-size:0.8rem;color:var(--text-muted);line-height:1.6;margin:4px 0 0">{c["text"][:400]}{"…" if len(c["text"]) > 400 else ""}</p>', unsafe_allow_html=True)

    # ── 输入框 ─────────────────────────────────────────────────────────────────
    question = st.chat_input("输入你的问题…")
    if not question:
        return

    _safe_q = question.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f'<div class="msg-row-user"><div class="bubble-user">{_safe_q}</div></div>',
        unsafe_allow_html=True,
    )
    st.session_state.rag_messages.append({"role": "user", "content": question})

    st.markdown('<div class="asst-bubble-marker"></div>', unsafe_allow_html=True)
    with st.spinner("检索知识库并生成回答…"):
        try:
            chunks = engine.query(question)
            answer = engine.generate_answer(question, chunks, st.session_state.rag_messages[:-1])
        except Exception as e:
            answer = f"出错：{e}"
            chunks = []

    st.markdown(answer)
    if chunks:
        with st.expander(f"参考来源（{len(chunks)} 条）"):
            for i, c in enumerate(chunks, 1):
                st.markdown(f"**{i}. {c['source']} · 第{c['page']}页** （相关度 {1 - c['distance']:.0%}）")
                st.text(c["text"][:400] + ("…" if len(c["text"]) > 400 else ""))

    st.session_state.rag_messages.append(
        {"role": "assistant", "content": answer, "chunks": chunks}
    )
    st.rerun()


engine = get_engine()
render_sidebar(engine)
render_chat(engine)
