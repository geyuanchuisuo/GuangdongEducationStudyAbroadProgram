"""知识检索接口契约（独立 /knowledge，2026-10-24 一期）。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512, description="检索问题")
    top_k: int = Field(5, ge=1, le=20, description="返回条数，默认 5")
    categories: list[str] | None = Field(
        None, description="可选：限定知识分类（公司信息/公司业务/留学政策），不传=全库"
    )
    with_score: bool = Field(True, description="是否返回相关度分数")


class KnowledgeItem(BaseModel):
    content: str = Field(..., description="命中的知识切片原文")
    category: str = Field(..., description="知识分类：公司信息/公司业务/留学政策")
    source_file: str = Field(..., description="来源文件名")
    section: str = Field(..., description="来源章节（FAQ 为原问题）")
    doc_type: str = Field(..., description="切片类型：faq=问答对 / doc=长文")
    score: float | None = Field(None, description="相关度分数（RRF 融合排名分）")


class KnowledgeSearchResponse(BaseModel):
    kb_source: str = Field(
        ..., description='检索来源："milvus"=正常；"unavailable"=向量库/嵌入服务不可用（结果为空）'
    )
    items: list[KnowledgeItem] = Field(default_factory=list)
    total: int = Field(0, description="本次返回条数")
