from __future__ import annotations

from io import BytesIO
from pathlib import Path


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md", ".markdown")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        return _extract_pdf_text(data)
    if name.endswith(".docx"):
        return _extract_docx_text(data)
    raise ValueError(f"Unsupported PRD file type: {filename}")


def extract_text_from_path(path: str | Path) -> str:
    path = Path(path)
    return extract_text_from_bytes(path.read_bytes(), path.name)


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF support requires pypdf. Install requirements.txt or upload TXT/MD.") from exc

    reader = PdfReader(BytesIO(data))
    parts = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            parts.append(f"[Page {index}]\n{text}")
    return "\n\n".join(parts)


def _extract_docx_text(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "DOCX support requires python-docx. Install it or upload PDF/TXT/MD."
        ) from exc

    doc = Document(BytesIO(data))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())
