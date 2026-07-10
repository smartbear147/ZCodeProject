"""测试文档解析：PDF / MD -> 纯文本。"""

import io

import pytest

from app.services.doc_parser import UnsupportedFormatError, parse_document


def test_parse_markdown_returns_utf8_text():
    content = "# 面试题\n\n- 自我介绍\n- 项目经历".encode("utf-8")
    text = parse_document("questions.md", content)
    assert text == "# 面试题\n\n- 自我介绍\n- 项目经历"


def test_parse_markdown_preserves_formatting():
    """markdown 符号（#/代码块）应原样保留。"""
    content = b"```python\nprint(1)\n```"
    assert parse_document("note.md", content) == "```python\nprint(1)\n```"


def test_parse_unsupported_format_raises():
    with pytest.raises(UnsupportedFormatError):
        parse_document("note.docx", b"...")


def test_parse_pdf_extracts_text():
    """用 pypdf 生成一个空白页 PDF，验证能正常调用且返回字符串。"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    text = parse_document("resume.pdf", buf.getvalue())
    assert isinstance(text, str)
    # 空白页提取出的文本为空字符串是正常的
    assert text == ""
