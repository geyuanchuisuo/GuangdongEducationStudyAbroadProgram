"""教育服务知识资料导入 Milvus（手动执行，幂等）。

用法（backend 目录下）：
    python -m scripts.ingest_knowledge              # 全量导入（按 source_file 先删后插）
    python -m scripts.ingest_knowledge --dry-run    # 只解析统计，不写库
    python -m scripts.ingest_knowledge --docs-dir "D:/xxx/docs/教育服务"   # 自定义资料目录

v6.14.0 双集合：FAQ 问答对（xlsx）→ 独立集合 yuejiao_faq（仅 question 向量化）；
md/docx 长文 → yuejiao_knowledge；两库并行维护，互不重复。

分类目录：公司信息 / 公司业务 / 留学政策 → category 字段（即检索过滤值）。
前置条件：Milvus（vector/start.bat）与 Ollama（bge-m3 模型）已启动。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.utils.knowledge_chunker import CATEGORIES, parse_file, parse_qa_pairs_xlsx
from app.utils.logger import logger

# 相对资料目录默认基于 backend 运行目录（python -m scripts.*）
DEFAULT_DOCS_DIR = Path(settings.KNOWLEDGE_DOCS_DIR)
# 跳过的资料文件：xlsx 的文本副本（内容同源，避免重复切片）
SKIP_FILES = {"问答对文本版.txt"}


def collect_files(docs_dir: Path) -> list[tuple[Path, str]]:
    """返回 (文件, 分类) 列表，分类 = 教育服务下的一级目录名。"""
    result: list[tuple[Path, str]] = []
    for category in CATEGORIES:
        folder = docs_dir / category
        if not folder.is_dir():
            logger.warning("分类目录不存在，跳过: %s", folder)
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.suffix.lower() in (".md", ".docx", ".xlsx", ".txt"):
                if path.name in SKIP_FILES:
                    continue
                result.append((path, category))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="教育服务知识资料导入 Milvus")
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR), help="教育服务资料目录")
    parser.add_argument("--dry-run", action="store_true", help="只解析统计，不写库")
    args = parser.parse_args()

    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        print(f"[ERROR] 资料目录不存在: {docs_dir}")
        return 1

    files = collect_files(docs_dir)
    if not files:
        print(f"[ERROR] 目录下没有可导入的资料: {docs_dir}")
        return 1

    # 延迟导入：dry-run 不依赖 Milvus/Ollama
    from app.services.knowledge_service import knowledge_service

    if not args.dry_run:
        knowledge_service.ensure_collection()
        knowledge_service.ensure_faq_collection()

    total_chunks = 0
    total_qa = 0
    stats: list[tuple[str, str, str, int]] = []  # (category, file, 库, 条数)
    for path, category in files:
        if path.suffix.lower() == ".xlsx":
            # 问答对 → 独立 FAQ 集合（仅 question 向量化）
            pairs = parse_qa_pairs_xlsx(str(path), category=category, source_file=path.name)
            if args.dry_run:
                stats.append((category, path.name, "faq", len(pairs)))
                total_qa += len(pairs)
                continue
            # v6.14.0 迁移：同时从长文集合剔除该文件旧 FAQ 切片（双库不再重复）
            knowledge_service.delete_by_source(path.name)
            knowledge_service.delete_faq_by_source(path.name)
            inserted = knowledge_service.upsert_qa_pairs(pairs)
            stats.append((category, path.name, "faq", inserted))
            total_qa += inserted
            print(f"  [{category}] {path.name} → faq 集合: {inserted} 条问答对")
            continue

        chunks = parse_file(str(path), category=category, source_file=path.name)
        if args.dry_run:
            stats.append((category, path.name, "knowledge", len(chunks)))
            total_chunks += len(chunks)
            continue
        knowledge_service.delete_by_source(path.name)
        inserted = knowledge_service.upsert_chunks(chunks)
        stats.append((category, path.name, "knowledge", inserted))
        total_chunks += inserted
        print(f"  [{category}] {path.name} → knowledge 集合: {inserted} 条切片")

    mode = "（dry-run，未写库）" if args.dry_run else ""
    print(f"\n导入完成{mode}：长文 {total_chunks} 条（knowledge 集合）+ 问答对 {total_qa} 条（faq 集合）")
    by_cat: dict[str, int] = {}
    for category, _, _, n in stats:
        by_cat[category] = by_cat.get(category, 0) + n
    for category in CATEGORIES:
        print(f"  {category}: {by_cat.get(category, 0)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
