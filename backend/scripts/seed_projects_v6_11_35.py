"""v6.11.35：course_project 业务口径修正（幂等）。

背景：seed_data 造的 15 条是雅思/托福/SAT 等培训课程（category 随机"语言培训/学科辅导"），
与项目需求文档口径（四大业务线：新加坡国际本硕升学 / 德国双元制职业教育 / 国际留学 / 国际研学，
核心产品《新加坡国际本硕升学计划》《中德精英人才共建计划》）不符，主页"业务项目"观感杂乱。

做法：按 id 顺序原位重写 project_name/category/description（保留 id，cs_recommend_log.course_id 外键不断），
学费/学制/状态保留原值。可重复执行（内容固定）。
执行：docker exec edu-backend /app/.venv/bin/python -m scripts.seed_projects_v6_11_35
"""

import asyncio

from sqlalchemy import select

from app.database import async_session_factory
from app.models.course import CourseProject

BUSINESS_PROJECTS = [
    ("新加坡国际本硕升学", "2+2 新加坡定向培养本科班", "国内2年+新加坡2年，对接新加坡院校，获海外学士学位。"),
    ("新加坡国际本硕升学", "2+2+1 本硕连读", "本科2+2衔接1年硕士，5年完成本硕学历。"),
    ("新加坡国际本硕升学", "0.5/1+2 新加坡定向培养本科班", "国内0.5或1年语言与基础课程，衔接新加坡2年本科。"),
    ("新加坡国际本硕升学", "0.5/1+2+1 本硕连读", "短国内阶段衔接新加坡本科+硕士连读。"),
    ("新加坡国际本硕升学", "一年制专升本项目", "大专毕业生1年获取新加坡本科学位。"),
    ("新加坡国际本硕升学", "一年制本升硕项目", "本科毕业生1年获取新加坡硕士学位。"),
    ("新加坡国际本硕升学", "6+6 酒店运营大专就业班", "6个月国内+6个月新加坡，酒店管理方向就业导向。"),
    ("新加坡国际本硕升学", "9+6 航空运营大专就业班", "9个月国内+6个月新加坡，航空服务方向就业导向。"),
    ("德国双元制职业教育", "中德精英人才共建计划", "德国双元制职业教育：企业带薪实习与职业院校双轨培养，毕业衔接就业。"),
    ("德国双元制职业教育", "德国双元制护理方向", "护理专业双元制培养，毕业衔接德国医疗机构就业。"),
    ("德国双元制职业教育", "德国双元制机电工程方向", "机电工程双元制培养，毕业衔接德国制造企业就业。"),
    ("国际留学", "全球院校申请服务", "覆盖全球主流目的地的院校匹配、文书与申请服务。"),
    ("国际留学", "背景提升与规划服务", "科研/实习/竞赛背景提升与长期留学规划。"),
    ("国际研学", "国际研学项目", "面向中小学生、高职高专及大学生的名校课堂、企业访学与文化浸润。"),
    ("国际研学", "海外名校暑期课堂", "暑期名校课程与城市探索研学。"),
]


async def main() -> None:
    async with async_session_factory() as session:
        rows = (
            await session.execute(select(CourseProject).order_by(CourseProject.id))
        ).scalars().all()
        updated = 0
        for i, row in enumerate(rows):
            if i >= len(BUSINESS_PROJECTS):
                break
            category, name, desc = BUSINESS_PROJECTS[i]
            row.category = category
            row.project_name = name
            row.description = desc
            updated += 1
        await session.commit()
        print(f"done: course_project updated={updated}, total_rows={len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
