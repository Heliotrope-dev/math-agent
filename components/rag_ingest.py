"""文档解析与切分 — PDF / TXT / Markdown。"""

import re

import fitz

from components.config import OCR_MODEL, get_secret

_MAX_OCR_PAGES = 30  # 扫描版 PDF 逐页跑视觉模型 OCR，封顶页数防止超大文件耗时/费用失控


def _ocr_page_text(image_bytes: bytes) -> str:
    """用视觉模型识别一页 PDF 渲染图里的全部文字（通用文档OCR）。

    不走 MathAgent.solve()——它固定带着"你是数学助教"的系统提示词，会把任何图片
    都往"找数学题"上带偏（实测：喂一张简历图片进去，模型会回复"未找到数学题"，
    完全无视了要求它做通用文字识别的用户指令）。这里直接调 API，不带那层系统提示词。
    """
    import base64
    import httpx
    from openai import OpenAI
    from tools import compress_image

    key = get_secret("SILICONFLOW_API_KEY")
    image_bytes = compress_image(image_bytes, max_size=1600, quality=85)
    b64 = base64.b64encode(image_bytes).decode()
    client = OpenAI(
        api_key=key,
        base_url="https://api.siliconflow.cn/v1",
        http_client=httpx.Client(trust_env=False, verify=True, timeout=httpx.Timeout(60.0, connect=15.0)),
    )
    resp = client.chat.completions.create(
        model=OCR_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "请识别并逐字输出这张图片里的所有文字内容，保持原有段落顺序，"
                    "不要总结、不要遗漏、不要额外解读，只输出识别到的文字原文；"
                    "如果这页没有任何文字，只输出：（空白页）"
                )},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


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

        if not docs:
            # 没有可提取的文字层——大概率是扫描版，或文字被设计工具拍平成图片/轮廓。
            # 逐页渲染成图片，走视觉模型 OCR 兜底。
            if not get_secret("SILICONFLOW_API_KEY"):
                raise ValueError(
                    f"「{filename}」没有可提取的文本，可能是扫描版 PDF；"
                    "OCR 兜底识别需要配置 SILICONFLOW_API_KEY，当前未配置。"
                )
            n_pages = min(pdf.page_count, _MAX_OCR_PAGES)
            for page_no in range(n_pages):
                pix = pdf[page_no].get_pixmap(dpi=150)
                img_bytes = pix.tobytes("jpeg")
                text = _ocr_page_text(img_bytes).strip()
                if text and text != "（空白页）" and not text.startswith("识别失败"):
                    docs.append({"text": text, "source": filename, "page": page_no + 1})
            if pdf.page_count > _MAX_OCR_PAGES:
                docs.append({
                    "text": f"（注意：本文档共 {pdf.page_count} 页，OCR 兜底仅识别了前 {_MAX_OCR_PAGES} 页）",
                    "source": filename, "page": _MAX_OCR_PAGES + 1,
                })
    finally:
        pdf.close()
    if not docs:
        raise ValueError(f"「{filename}」没有可提取的文本，OCR 兜底也未能识别到任何内容。")
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
