"""knowledge_chunker 单元测试：切片策略（FAQ 整对切 / md·docx 标题切 / 长文滑窗）。"""

from pathlib import Path

from openpyxl import Workbook

from app.utils.knowledge_chunker import (
    CHUNK_OVERLAP_CHARS,
    CHUNK_TARGET_CHARS,
    make_chunk_id,
    parse_file,
    parse_markdown,
    parse_qa_txt,
    parse_qa_xlsx,
    split_long_text,
)


def test_split_short_text_single_chunk():
    assert split_long_text("粤教服务") == ["粤教服务"]
    assert split_long_text("   ") == []


def test_split_long_text_window_and_bounds():
    # 一整段无标点长文 → 硬切滑窗；每片不超 target+overlap，相邻片有重叠
    text = "字" * (CHUNK_TARGET_CHARS * 3)
    chunks = split_long_text(text)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= CHUNK_TARGET_CHARS + CHUNK_OVERLAP_CHARS


def test_split_long_text_sentence_boundary():
    # 有标点的长文优先在句末断开：每片以句终符号结尾（末片除外）
    sentence = "这是一句完整的话，包含前半句和后半句。"
    text = sentence * 40
    chunks = split_long_text(text)
    assert len(chunks) > 1
    for c in chunks[:-1]:
        assert c.endswith(("。", "！", "？", "；"))


def test_markdown_sections_and_title_in_content():
    md = "\n".join([
        "顶部引言，出现在任何标题之前。",
        "# 公司信息",
        "这是公司信息的总介绍。",
        "## 部门架构",
        "双元制事业部负责德国双元制教育。",
        "### 双元制事业部",
        "专注德国职业培训推广。",
    ])
    chunks = parse_markdown(md, category="公司信息", source_file="企业信息.md")
    assert len(chunks) == 4
    # 首个标题前的引言 → 无标题归属，section 兜底为文件名
    assert chunks[0].section == "企业信息.md"
    assert "顶部引言" in chunks[0].content
    # 二级/三级标题路径，且标题并入内容首行（利于召回）
    assert chunks[2].section == "公司信息 / 部门架构"
    assert chunks[2].content.startswith("公司信息 / 部门架构")
    assert chunks[3].section == "公司信息 / 部门架构 / 双元制事业部"
    assert all(c.category == "公司信息" for c in chunks)


def test_qa_txt_one_pair_one_chunk():
    text = "公司简称是什么？\t简称“粤教服务”\n德国项目优势？\t国企直签。\n\n没有制表符的行应被忽略\n"
    chunks = parse_qa_txt(text, category="公司信息", source_file="问答对文本版.txt")
    assert len(chunks) == 2
    assert all(c.doc_type == "faq" for c in chunks)
    assert chunks[0].content == "公司简称是什么？\n简称“粤教服务”"
    assert chunks[0].section == "公司简称是什么？"


def test_qa_xlsx_header_detect(tmp_path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["问题", "答案"])
    ws.append(["新加坡项目学费多少？", "总计约 25 万人民币。"])
    ws.append([None, None])  # 空行跳过
    path = tmp_path / "常见问答对.xlsx"
    wb.save(path)

    chunks = parse_qa_xlsx(str(path), category="公司信息", source_file=path.name)
    assert len(chunks) == 1
    assert chunks[0].doc_type == "faq"
    assert "25 万" in chunks[0].content


def test_parse_docx_headings_and_table(tmp_path: Path):
    from docx import Document

    doc = Document()
    doc.add_heading("新加坡留学政策指南", level=1)
    doc.add_paragraph("新加坡是热门留学目的地。")
    doc.add_heading("签证要求", level=2)
    doc.add_paragraph("需要提供资金证明与录取通知书。")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "项目"
    table.cell(0, 1).text = "学费"
    table.cell(1, 0).text = "国际本科班"
    table.cell(1, 1).text = "约 30 万"
    path = tmp_path / "新加坡留学政策指南.docx"
    doc.save(path)

    chunks = parse_file(str(path), category="留学政策", source_file=path.name)
    assert len(chunks) == 2
    assert chunks[0].section == "新加坡留学政策指南"
    assert chunks[1].section == "新加坡留学政策指南 / 签证要求"
    # 表格行并入当前 section
    assert "国际本科班 | 约 30 万" in chunks[1].content
    assert all(c.category == "留学政策" for c in chunks)


def test_chunk_id_deterministic_and_sensitive():
    a = make_chunk_id("公司信息", "faq", "问\n答")
    assert a == make_chunk_id("公司信息", "faq", "问\n答")
    assert a != make_chunk_id("公司业务", "faq", "问\n答")
    assert a != make_chunk_id("公司信息", "doc", "问\n答")
    assert len(a) == 32
