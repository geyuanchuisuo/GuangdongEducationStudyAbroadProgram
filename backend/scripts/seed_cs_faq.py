"""
客服 FAQ 种子脚本 — 将《常见问答对》36 组 + 退费红线 QA 1 条导入 cs_faq（幂等，按 question 去重）。

数据源: scripts/cs_faq_seed.json（由 docs/教育服务/公司信息/问答对文本版.txt 转换 + 退费 QA 补漏）
用法: python -m scripts.seed_cs_faq
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session_factory
from app.models.customer_service import CsFaq

SEED_FILE = Path(__file__).with_name("cs_faq_seed.json")


async def seed():
    rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    async with async_session_factory() as session:
        existing = {q for (q,) in (await session.execute(select(CsFaq.question))).all()}
        created = 0
        for sort_order, row in enumerate(rows):
            if row["question"] in existing:
                continue
            session.add(
                CsFaq(
                    category=row.get("category"),
                    question=row["question"],
                    answer=row["answer"],
                    sort_order=sort_order,
                    enabled=True,
                )
            )
            created += 1
        await session.commit()
    print(f"FAQ 种子完成：新增 {created} 条（种子共 {len(rows)} 条，已存在 {len(rows) - created} 条跳过）")


if __name__ == "__main__":
    asyncio.run(seed())
