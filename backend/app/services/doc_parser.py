"""文档解析：按扩展名把上传文件转成纯文本。

- PDF (.pdf)：用 pypdf 提取文本
- Markdown (.md)：UTF-8 解码，保留 markdown 格式（帮 LLM 理解结构）
- 其它：抛 UnsupportedFormatError
"""

import io

from pypdf import PdfReader


class UnsupportedFormatError(ValueError):
    """上传了不支持的文件格式。"""


def parse_document(filename: str, file_bytes: bytes) -> str:
    """按扩展名解析文档，返回纯文本。

    Args:
        filename: 原始文件名（用于判断扩展名）。
        file_bytes: 文件原始字节。

    Returns:
        解析出的纯文本。

    Raises:
        UnsupportedFormatError: 不支持的格式。
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        return _parse_pdf(file_bytes)
    if name.endswith(".md"):
        return file_bytes.decode("utf-8")
    raise UnsupportedFormatError(f"不支持的文件格式: {filename}（仅支持 .pdf / .md）")


def _parse_pdf(file_bytes: bytes) -> str:
    """用 pypdf 提取 PDF 全部页面的文本。"""
    reader = PdfReader(io.BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()
