"""
客服 FAQ 种子脚本 — 将《常见问答对》36 组 + 退费红线 QA 1 条导入 cs_faq。

数据源: scripts/cs_faq_seed.json（由 docs/教育服务/公司信息/问答对文本版.txt 转换 + 退费 QA 补漏）
用法: python -m scripts.seed_cs_faq
幂等策略: 按 question upsert（新增 / 原位更新 category/answer/keywords/sort_order）；
        旧问法经 QUESTION_RENAMES 原位改名，不产生重复行。第二次运行应零变更。
注意: scripts/seed_data.py 会 drop_all 重建全库（清空本表），重建后需重跑本脚本补种 FAQ。
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database import async_session_factory
from app.models.customer_service import CsFaq

SEED_FILE = Path(__file__).with_name("cs_faq_seed.json")

# 历史问法迁移：旧库中已按旧问法入座的行，首次跑到新版种子时原位改名（幂等）
QUESTION_RENAMES = {"公司简称什么?": "公司简称是什么？"}


async def seed():
    rows = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    async with async_session_factory() as session:
        # 1) 旧问法原位改名（新问法已存在时不重复迁移，避免撞唯一问法）
        renamed = 0
        for old, new in QUESTION_RENAMES.items():
            row = (await session.execute(select(CsFaq).where(CsFaq.question == old))).scalar_one_or_none()
            if row is None:
                continue
            if (await session.execute(select(CsFaq).where(CsFaq.question == new))).scalar_one_or_none():
                continue
            row.question = new
            renamed += 1
            print(f"问法迁移：{old!r} → {new!r}")
        await session.flush()

        # 2) 按 question upsert：已存在则原位更新（有变化才写），否则新增
        existing = {row.question: row for row in (await session.execute(select(CsFaq))).scalars()}
        created = updated = 0
        for sort_order, data in enumerate(rows):
            fields = {
                "category": data.get("category"),
                "answer": data["answer"],
                "keywords": data.get("keywords"),
                "sort_order": sort_order,
                "enabled": True,
            }
            row = existing.get(data["question"])
            if row is None:
                session.add(CsFaq(question=data["question"], **fields))
                created += 1
                continue
            changed = {k: v for k, v in fields.items() if getattr(row, k) != v}
            if changed:
                for k, v in changed.items():
                    setattr(row, k, v)
                updated += 1
                print(f"原位更新：{data['question']}（{'、'.join(changed)}）")
        await session.commit()
    print(f"FAQ 种子完成：新增 {created} 条、原位更新 {updated} 条、问法迁移 {renamed} 条（种子共 {len(rows)} 条）")


if __name__ == "__main__":
    asyncio.run(seed())
