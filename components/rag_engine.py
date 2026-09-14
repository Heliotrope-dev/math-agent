"""RAG 核心引擎 — 向量检索 + Gemini 生成。"""

import logging
import os
from pathlib import Path

import chromadb
from openai import OpenAI

from components.config import DEFAULT_MODEL, GEMINI_EMBED_MODEL, get_secret, build_gemini_failover_client

_log = logging.getLogger(__name__)

_CHROMA_DIR    = str(Path(__file__).parent.parent / "data" / "chroma_db")
_COLLECTION    = "rag_knowledge_base"
_EMBED_BATCH   = 16
_TOP_K         = 4
_MAX_HIST      = 5

_SYSTEM = """你是知识库助手，只根据提供的参考资料回答问题。
如果资料中找不到相关信息，直接说"文档中未找到相关内容"，不要编造。

回答要求：
- 用中文回答，条理清晰
- 引用资料时忠于原文，不夸大、不推测
- 答案末尾单独一行列出用到的来源，格式：参考来源：文件名 第X页"""


class RAGEngine:
    def __init__(self) -> None:
        os.makedirs(_CHROMA_DIR, exist_ok=True)
        self._chroma = chromadb.PersistentClient(path=_CHROMA_DIR)
        self.collection = self._chroma.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._llm = None

    def _client(self):
        # Gemini 免费→付费故障转移，两把key打包在一个客户端里，不用再
        # 靠"key变了就重建"这种脏检查（GeminiFailoverClient内部自己处理
        # 两把key的切换）。
        if self._llm is None:
            self._llm = build_gemini_failover_client(max_retries=2)
        return self._llm

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """2026-09-14从SiliconFlow bge-m3切到Gemini gemini-embedding-001：
        knowledge base当时是空的，没有旧向量兼容问题，直接换，不用数据迁移。
        复用文字/拍题/语音那同一个GeminiFailoverClient。
        """
        if not (get_secret("GEMINI_API_KEY") or get_secret("GEMINI_FREE_API_KEY")):
            raise RuntimeError("未配置 GEMINI_API_KEY，无法生成向量。")
        client = self._client()
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i: i + _EMBED_BATCH]
            try:
                resp = client.embeddings.create(model=GEMINI_EMBED_MODEL, input=batch)
            except Exception as e:
                raise RuntimeError(f"向量化失败（第 {i // _EMBED_BATCH + 1} 批）：{e}") from e
            # 实测Gemini这个接口batch请求返回的第一条index是None（其余正常
            # 从1开始），不能像OpenAI那样按index排序——直接信任列表顺序等于
            # 输入顺序（embeddings接口的通行约定，也是实测观察到的行为）。
            vectors.extend(d.embedding for d in resp.data)
        return vectors

    def add_documents(self, chunks: list[dict], source_name: str, user: str) -> int:
        if not chunks:
            return 0
        self.delete_document(source_name, user)
        embeddings = self.embed_texts([c["text"] for c in chunks])
        self.collection.add(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "page": c["page"], "user": user} for c in chunks],
        )
        return len(chunks)

    def delete_document(self, source_name: str, user: str) -> None:
        try:
            self.collection.delete(where={"$and": [{"source": source_name}, {"user": user}]})
        except Exception as e:
            _log.warning("删除文档 %s（用户 %s）失败: %s", source_name, user, e)

    def list_documents(self, user: str) -> dict[str, int]:
        try:
            records = self.collection.get(where={"user": user}, include=["metadatas"])
        except Exception as e:
            _log.warning("读取文档列表失败: %s", e)
            return {}
        counts: dict[str, int] = {}
        for meta in records.get("metadatas") or []:
            src = (meta or {}).get("source", "未知来源")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def user_chunk_count(self, user: str) -> int:
        try:
            records = self.collection.get(where={"user": user}, include=[])
        except Exception as e:
            _log.warning("统计用户文档数失败: %s", e)
            return 0
        return len(records.get("ids") or [])

    def query(self, question: str, user: str, top_k: int = _TOP_K) -> list[dict]:
        n_available = self.user_chunk_count(user)
        if n_available == 0:
            return []
        vector = self.embed_texts([question])[0]
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, n_available),
            where={"user": user},
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for text, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            chunks.append({
                "text":     text,
                "source":   (meta or {}).get("source", "未知来源"),
                "page":     (meta or {}).get("page", 1),
                "distance": round(dist, 4),
            })
        return chunks

    def generate_answer(self, question: str, chunks: list[dict], history: list) -> str:
        if not get_secret("GEMINI_FREE_API_KEY") and not get_secret("GEMINI_API_KEY"):
            raise RuntimeError("未配置 GEMINI_FREE_API_KEY / GEMINI_API_KEY。")
        context_lines = []
        for i, c in enumerate(chunks, 1):
            context_lines.append(f"【资料{i}】（来源：{c['source']} 第{c['page']}页）\n{c['text']}")
        context = "\n\n".join(context_lines) if context_lines else "（知识库中没有检索到相关资料）"
        messages = [{"role": "system", "content": _SYSTEM}]
        recent = history[-_MAX_HIST * 2:] if history else []
        for msg in recent:
            if msg.get("role") in ("user", "assistant") and isinstance(msg.get("content"), str):
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": f"参考资料：\n{context}\n\n问题：{question}"})
        try:
            resp = self._client().chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                max_tokens=2048,
            )
        except Exception as e:
            raise RuntimeError(f"回答生成失败：{e}") from e
        return resp.choices[0].message.content or "（无输出）"
