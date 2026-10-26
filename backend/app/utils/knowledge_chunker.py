"""教育服务知识资料解析与切片（知识库混合检索一期）。

把 docs/教育服务 下三类资料（公司信息/公司业务/留学政策）解析成统一的
知识切片 KnowledgeChunk，供 scripts/ingest_knowledge.py 导入 Milvus。

切片策略（2026-10-24 方案确认稿）：
- FAQ 问答对（常见问答对.xlsx）：一问一答一个切片，不切碎；
- Markdown 长文：按标题层级切 section，section 标题并入切片首行；
- docx 指南：按 Heading/标题 样式切 section（表格行并入当前 section），
  超长 section 按 ~500 字滑窗（重叠 80 字，优先句子边界）。

纯函数实现，不依赖 Milvus/Ollama，可独立单测。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# 长文滑窗参数
CHUNK_TARGET_CHARS = 500
CHUNK_OVERLAP_CHARS = 80
_SLACK_CHARS = 50          # 允许少量超出目标长度，避免为几十个字硬切
_MAX_SECTION_TITLE = 200   # section 字段落库截断长度

# 知识分类 = 教育服务下的目录名
CATEGORIES = ("公司信息", "公司业务", "留学政策")

# doc_type：faq=问答对切片；doc=长文切片（category 已区分信息/业务/政策）
DOC_TYPE_FAQ = "faq"
DOC_TYPE_DOC = "doc"

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；\n])")
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_DOCX_HEADING = re.compile(r"^(?:heading|标题)\s*(\d+)$", re.IGNORECASE)


@dataclass
class KnowledgeChunk:
    """一条知识切片。chunk_id 为内容哈希，导入按 source_file 先删后插实现幂等。"""

    chunk_id: str
    content: str
    category: str
    source_file: str
    section: str
    doc_type: str


@dataclass
class QAPair:
    """一条问答对（v6.14.0 独立 FAQ 集合用）：仅 question 参与向量化。"""

    question: str
    answer: str
    category: str
    source_file: str

    @property
    def chunk_id(self) -> str:
        return make_chunk_id(self.category, DOC_TYPE_FAQ, self.question)


def make_chunk_id(category: str, doc_type: str, content: str) -> str:
    return hashlib.md5(f"{category}|{doc_type}|{content}".encode("utf-8")).hexdigest()


def split_long_text(
    text: str,
    target: int = CHUNK_TARGET_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """长文本滑窗切片：优先在句子边界（。！？；换行）断开，相邻切片保留重叠。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= target + _SLACK_CHARS:
        return [text]

    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if buf and len(buf) + len(s) > target:
            chunks.append(buf)
            buf = buf[-overlap:] if overlap else ""
        buf += s
        # 无标点的超长句：按 target 硬切，尾部保留 overlap
        while len(buf) > target + overlap:
            chunks.append(buf[:target])
            buf = buf[target - overlap:] if target > overlap else ""
    if buf.strip():
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


def _build_chunks(
    sections: list[tuple[str, str]],
    *,
    category: str,
    source_file: str,
    doc_type: str,
) -> list[KnowledgeChunk]:
    """(section 标题, 正文) 列表 → 切片列表；标题并入内容首行提升召回。"""
    chunks: list[KnowledgeChunk] = []
    for title, body in sections:
        if not body:
            continue
        section = (title or source_file)[:_MAX_SECTION_TITLE]
        for piece in split_long_text(body):
            content = f"{section}\n{piece}" if title else piece
            chunks.append(
                KnowledgeChunk(
                    chunk_id=make_chunk_id(category, doc_type, content),
                    content=content,
                    category=category,
                    source_file=source_file,
                    section=section,
                    doc_type=doc_type,
                )
            )
    return chunks


def parse_markdown(text: str, *, category: str, source_file: str) -> list[KnowledgeChunk]:
    """Markdown 按标题层级切 section（路径取前 3 级）。"""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, str]] = []
    title = ""
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((title, body))
        buf.clear()

    for line in text.splitlines():
        m = _MD_HEADING.match(line)
        if m:
            flush()
            level, text_ = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text_))
            title = " / ".join(t for _, t in stack[:3])
        else:
            buf.append(line)
    flush()
    return _build_chunks(sections, category=category, source_file=source_file, doc_type=DOC_TYPE_DOC)


def parse_docx(path: str, *, category: str, source_file: str) -> list[KnowledgeChunk]:
    """docx 按 Heading/标题 样式切 section，表格行转「单元格 | 单元格」并入当前 section。"""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(path)
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, str]] = []
    title = ""
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            sections.append((title, body))
        buf.clear()

    # python-docx >= 1.1 支持按文档顺序遍历段落+表格；旧版退化为仅段落
    try:
        inner = list(doc.iter_inner_content())
    except AttributeError:  # pragma: no cover - 依赖锁定 >=1.1，兜底路径
        inner = list(doc.paragraphs)

    for item in inner:
        if isinstance(item, Paragraph):
            style_name = (item.style.name or "").strip() if item.style is not None else ""
            m = _DOCX_HEADING.match(style_name)
            if m:
                flush()
                level, text_ = int(m.group(1)), item.text.strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, text_))
                title = " / ".join(t for _, t in stack[:3])
            elif item.text.strip():
                buf.append(item.text.strip())
        elif isinstance(item, Table):
            for row in item.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    buf.append(" | ".join(cells))
    flush()
    return _build_chunks(sections, category=category, source_file=source_file, doc_type=DOC_TYPE_DOC)


def _iter_qa_rows_xlsx(path: str):
    """xlsx 问答对行迭代器：列头含「问」/「答」定位两列（缺省前两列），yield (q, a)。"""
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        q_idx, a_idx = 0, 1
        if header:
            for i, cell in enumerate(header):
                name = str(cell) if cell is not None else ""
                if "问" in name:
                    q_idx = i
                elif "答" in name:
                    a_idx = i
        for row in rows:
            q = str(row[q_idx]).strip() if q_idx < len(row) and row[q_idx] is not None else ""
            a = str(row[a_idx]).strip() if a_idx < len(row) and row[a_idx] is not None else ""
            if q or a:
                yield q, a
    finally:
        wb.close()


def parse_qa_pairs_xlsx(path: str, *, category: str, source_file: str) -> list[QAPair]:
    """问答对 xlsx → QAPair 列表（v6.14.0 独立 FAQ 集合：仅 question 向量化）。"""
    return [
        QAPair(question=q, answer=a, category=category, source_file=source_file)
        for q, a in _iter_qa_rows_xlsx(path)
    ]


def parse_qa_xlsx(path: str, *, category: str, source_file: str) -> list[KnowledgeChunk]:
    """问答对 xlsx：一行一问一答一个切片（旧单库模式的兼容入口，测试仍在用）。"""
    chunks: list[KnowledgeChunk] = []
    for q, a in _iter_qa_rows_xlsx(path):
        content = f"{q}\n{a}".strip()
        chunks.append(
            KnowledgeChunk(
                chunk_id=make_chunk_id(category, DOC_TYPE_FAQ, content),
                content=content,
                category=category,
                source_file=source_file,
                section=q[:100] or a[:100],
                doc_type=DOC_TYPE_FAQ,
            )
        )
    return chunks


def parse_qa_txt(text: str, *, category: str, source_file: str) -> list[KnowledgeChunk]:
    """问答对 txt（制表符分隔，问答对文本版.txt 的格式）：一行一问一答。"""
    chunks: list[KnowledgeChunk] = []
    for line in text.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        q, a = parts[0].strip(), parts[1].strip()
        if not q and not a:
            continue
        content = f"{q}\n{a}".strip()
        chunks.append(
            KnowledgeChunk(
                chunk_id=make_chunk_id(category, DOC_TYPE_FAQ, content),
                content=content,
                category=category,
                source_file=source_file,
                section=q[:100] or a[:100],
                doc_type=DOC_TYPE_FAQ,
            )
        )
    return chunks


def parse_file(path: str, *, category: str, source_file: str) -> list[KnowledgeChunk]:
    """按扩展名分派解析器。"""
    if path.lower().endswith(".md"):
        with open(path, encoding="utf-8") as f:
            return parse_markdown(f.read(), category=category, source_file=source_file)
    if path.lower().endswith(".docx"):
        return parse_docx(path, category=category, source_file=source_file)
    if path.lower().endswith(".xlsx"):
        return parse_qa_xlsx(path, category=category, source_file=source_file)
    if path.lower().endswith(".txt"):
        with open(path, encoding="utf-8") as f:
            return parse_qa_txt(f.read(), category=category, source_file=source_file)
    return []
