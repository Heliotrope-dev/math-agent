"""文档解析与切分 — PDF / TXT / Markdown。"""

import re

import fitz


def parse_pdf(file_bytes: bytes, filename: str) -> list[dict]:
    docs = []
    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"PDF 解析失败（{filename}）：文件可能已损坏或加密。{e}") from e
    try:
        for page_no in range(pdf.page_count):
            text = pdf[page_no].get_text().strip()
            if not text:
                continue
            docs.append({"text": text, "source": filename, "page": page_no + 1})
    finally:
        pdf.close()
    if not docs:
        raise ValueError(f"「{filename}」没有可提取的文本，可能是扫描版 PDF。")
    return docs


def parse_txt(file_bytes: bytes, filename: str) -> list[dict]:
    text = None
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    if text is None or not text.strip():
        raise ValueError(f"「{filename}」内容为空或编码无法识别。")
    return [{"text": text.strip(), "source": filename, "page": 1}]


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    sentences = re.split(r"(?<=[。！？!?\n])", text)
    sentences = [s for s in sentences if s.strip()]
    pieces: list[str] = []
    buf = ""
    for sent in sentences:
        if len(sent) > chunk_size:
            if buf:
                pieces.append(buf)
                buf = ""
            step = chunk_size - overlap
            for i in range(0, len(sent), step):
                pieces.append(sent[i: i + chunk_size])
            continue
        if len(buf) + len(sent) > chunk_size:
            pieces.append(buf)
            buf = buf[-overlap:] + sent if overlap else sent
        else:
            buf += sent
    if buf.strip():
        pieces.append(buf)
    return [p.strip() for p in pieces if p.strip()]


def chunk_documents(docs: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    chunks = []
    for doc in docs:
        for piece in _split_long_text(doc["text"], chunk_size, overlap):
            chunks.append({
                "text":     piece,
                "source":   doc["source"],
                "page":     doc["page"],
                "chunk_id": f"{doc['source']}::p{doc['page']}::c{len(chunks)}",
            })
    return chunks
