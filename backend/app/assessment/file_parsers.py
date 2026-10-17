"""研判文件解析适配器。

此模块有意不接入现有 MinIO/上传链路：项目公共文件层尚未实现。上游上传层
将受控文件保存为临时路径后调用 ``extract_text``，再将结果传给文本研判接口。
"""
from __future__ import annotations

from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".csv", ".docx", ".xlsx", ".pdf"}


def extract_text(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型：{suffix}")
    if suffix in {".txt", ".md", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".docx":
        from docx import Document
        document = Document(file_path)
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(file_path, data_only=True, read_only=True)
        return "\n".join(
            " | ".join(str(value or "") for value in row)
            for sheet in workbook.worksheets
            for row in sheet.iter_rows(values_only=True)
        )
    # PyMuPDF is deliberately lazy-imported; add it to the project dependency
    # only when the public file-upload capability is approved.
    import pymupdf
    document = pymupdf.open(file_path)
    return "\n".join(page.get_text() for page in document)
