"""RAG 核心引擎 — 向量检索 + DeepSeek 生成。"""

import logging
import os
from pathlib import Path

import chromadb
import httpx
from openai import OpenAI

from components.config import DEFAULT_MODEL, SILICONFLOW_BASE, get_secret

_log = logging.getLogger(__name__)

_CHROMA_DIR    = str(Path(__file__).parent.parent / "data" / "chroma_db")
_COLLECTION    = "rag_knowledge_base"
_EMBED_MODEL   = "BAAI/bge-m3"
_EMBED_BATCH   = 16
_EMBED_TIMEOUT = 30
_TOP_K         = 4
_MAX_HIST      = 5
_DEEPSEEK_BASE = "https://api.deepseek.com"

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
        self._llm: OpenAI | None = None
        self._llm_key = ""

    def _client(self) -> OpenAI:
        key = get_secret("DEEPSEEK_API_KEY")
        if self._llm is None or key != self._llm_key:
            self._llm = OpenAI(api_key=key, base_url=_DEEPSEEK_BASE, max_retries=2)
            self._llm_key = key
        return self._llm

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        key = get_secret("SILICONFLOW_API_KEY")
        if not key:
            raise RuntimeError("未配置 SILICONFLOW_API_KEY，无法生成向量。")
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i: i + _EMBED_BATCH]
            try:
                resp = httpx.post(
                    f"{SILICONFLOW_BASE}/v1/embeddings",
                    headers={"Authorization": f"Bearer {key}"},
                    json={"model": _EMBED_MODEL, "input": batch},
                    timeout=_EMBED_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()["data"]
            except httpx.TimeoutException as e:
                raise RuntimeError(f"向量化请求超时（第 {i // _EMBED_BATCH + 1} 批）。") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"向量化接口错误 {e.response.status_code}：{e.response.text[:200]}"
                ) from e
            data.sort(key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)
        return vectors

    def add_documents(self, chunks: list[dict], source_name: str) -> int:
        if not chunks:
            return 0
        self.delete_document(source_name)
        embeddings = self.embed_texts([c["text"] for c in chunks])
        self.collection.add(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[{"source": c["source"], "page": c["page"]} for c in chunks],
        )
        return len(chunks)

    def delete_document(self, source_name: str) -> None:
        try:
            self.collection.delete(where={"source": source_name})
        except Exception as e:
            _log.warning("删除文档 %s 失败: %s", source_name, e)

    def list_documents(self) -> dict[str, int]:
        try:
            records = self.collection.get(include=["metadatas"])
        except Exception as e:
            _log.warning("读取文档列表失败: %s", e)
            return {}
        counts: dict[str, int] = {}
        for meta in records.get("metadatas") or []:
            src = (meta or {}).get("source", "未知来源")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def query(self, question: str, top_k: int = _TOP_K) -> list[dict]:
        if self.collection.count() == 0:
            return []
        vector = self.embed_texts([question])[0]
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, self.collection.count()),
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
        if not get_secret("DEEPSEEK_API_KEY"):
            raise RuntimeError("未配置 DEEPSEEK_API_KEY。")
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
