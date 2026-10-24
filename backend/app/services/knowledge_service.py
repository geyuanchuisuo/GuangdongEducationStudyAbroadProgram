"""知识库混合检索服务（独立 /knowledge，2026-10-24 一期）。

设计要点：
- Milvus 2.6 hybrid_search 双路混合：dense（Ollama bge-m3，1024 维，HNSW/COSINE，
  语义召回）+ sparse（Milvus 内置 BM25 Function，jieba 中文分词，关键词召回，
  覆盖 "2+2"/"IHK" 等专有名词），RRFRanker(k=60) 融合排序；
- 建表幂等（ensure_collection），collection 缺失自动创建，重复执行无副作用；
- 导入幂等：按 source_file 先删后插（scripts/ingest_knowledge.py），
  chunk_id 为内容哈希，同内容不会重复入库；
- Milvus / Ollama 不可用时返回 kb_source="unavailable" 空结果，沿用项目
  ai_source 三态口径，不抛 500；
- 本模块为独立新增文件，未改动任何 M0 共用组件（config 仅追加键）。
"""

from __future__ import annotations

import threading

from app.config import settings
from app.schemas.knowledge import KnowledgeItem, KnowledgeSearchResponse
from app.utils.knowledge_chunker import KnowledgeChunk
from app.utils.logger import logger

_INSERT_BATCH = 64
_EMBED_BATCH = 32


class KnowledgeService:
    """Milvus + Ollama 嵌入的封装；同步实现，FastAPI 端用 asyncio.to_thread 调用。"""

    def __init__(self, uri: str | None = None, collection: str | None = None) -> None:
        self._uri = uri or settings.MILVUS_URI
        self._collection = collection or settings.MILVUS_COLLECTION
        self._client = None
        self._lock = threading.Lock()

    # ---- 连接与建表 ---------------------------------------------------------

    def _get_client(self):
        with self._lock:
            if self._client is None:
                from pymilvus import MilvusClient

                self._client = MilvusClient(uri=self._uri)
            return self._client

    def ensure_collection(self) -> None:
        """collection 不存在则建（schema+索引+BM25 函数），已存在直接返回。"""
        client = self._get_client()
        if client.has_collection(self._collection):
            return

        from pymilvus import DataType, Function, FunctionType, MilvusClient

        schema = MilvusClient.create_schema()
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
        # BM25 输入字段需启用分析器；jieba 中文分词解决中文无空格切词问题
        # （Milvus v2.6 内置中文 tokenizer 名为 "jieba"）
        schema.add_field(
            "content",
            DataType.VARCHAR,
            max_length=4096,
            enable_analyzer=True,
            analyzer_params={"tokenizer": "jieba"},
        )
        schema.add_field(
            "category", DataType.VARCHAR, max_length=32, is_partition_key=True
        )
        schema.add_field("source_file", DataType.VARCHAR, max_length=256)
        schema.add_field("section", DataType.VARCHAR, max_length=512)
        schema.add_field("doc_type", DataType.VARCHAR, max_length=16)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=settings.EMBED_DIM)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="content_bm25",
                function_type=FunctionType.BM25,
                input_field_names=["content"],
                output_field_names=["sparse"],
            )
        )

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
        index_params.add_index(
            field_name="sparse",
            index_type="SPARSE_INVERTED_INDEX",
            # BM25 Function 输出字段的索引 metric 必须为 BM25（Milvus v2.6 校验强制）
            metric_type="BM25",
        )
        client.create_collection(
            self._collection, schema=schema, index_params=index_params
        )
        logger.info("知识库 collection 已创建: %s (%s)", self._collection, self._uri)

    # ---- 嵌入 ---------------------------------------------------------------

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """调 Ollama bge-m3 批量嵌入（单批 ≤ _EMBED_BATCH 条）。"""
        import ollama

        client = ollama.Client(host=settings.OLLAMA_BASE_URL, timeout=120.0)
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i : i + _EMBED_BATCH]
            resp = client.embed(model=settings.EMBED_MODEL, input=batch)
            vectors.extend(list(v) for v in resp["embeddings"])
        return vectors

    # ---- 导入 ---------------------------------------------------------------

    def delete_by_source(self, source_file: str) -> None:
        """按来源文件清空旧切片（导入前调用，实现按文件幂等重导）。"""
        client = self._get_client()
        client.delete(
            collection_name=self._collection,
            filter=f'source_file == "{source_file}"',
        )

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> int:
        """切片嵌入后写入 Milvus，返回写入条数。"""
        if not chunks:
            return 0
        self.ensure_collection()
        client = self._get_client()
        vectors = self.embed_texts([c.content for c in chunks])
        rows = [
            {
                "chunk_id": c.chunk_id,
                "content": c.content,
                "category": c.category,
                "source_file": c.source_file,
                "section": c.section,
                "doc_type": c.doc_type,
                "dense": vec,
            }
            for c, vec in zip(chunks, vectors)
        ]
        total = 0
        for i in range(0, len(rows), _INSERT_BATCH):
            batch = rows[i : i + _INSERT_BATCH]
            client.insert(collection_name=self._collection, data=batch)
            total += len(batch)
        return total

    # ---- 混合检索 -----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        categories: list[str] | None = None,
    ) -> KnowledgeSearchResponse:
        """稠密语义 + BM25 关键词双路召回，RRF 融合。

        Milvus/Ollama 任一不可用时返回 kb_source="unavailable"（空结果），
        由调用方按三态口径处理，不向上抛异常。
        """
        try:
            self.ensure_collection()
            client = self._get_client()
            query_vec = self.embed_texts([query])[0]

            from pymilvus import AnnSearchRequest, RRFRanker

            dense_req = AnnSearchRequest(
                data=[query_vec],
                anns_field="dense",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=top_k,
            )
            # BM25 Function 字段直接传查询原文，稀疏向量由 Milvus 服务端生成
            sparse_req = AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param={"metric_type": "BM25"},
                limit=top_k,
            )
            filter_expr = ""
            if categories:
                quoted = ", ".join(f'"{c}"' for c in categories)
                filter_expr = f"category in [{quoted}]"

            results = client.hybrid_search(
                collection_name=self._collection,
                reqs=[dense_req, sparse_req],
                ranker=RRFRanker(60),
                limit=top_k,
                filter=filter_expr or None,
                output_fields=["content", "category", "source_file", "section", "doc_type"],
            )
            items: list[KnowledgeItem] = []
            for hit in results[0]:
                entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
                items.append(
                    KnowledgeItem(
                        content=entity.get("content", ""),
                        category=entity.get("category", ""),
                        source_file=entity.get("source_file", ""),
                        section=entity.get("section", ""),
                        doc_type=entity.get("doc_type", ""),
                        score=float(hit.get("distance", 0.0)) if isinstance(hit, dict) else 0.0,
                    )
                )
            return KnowledgeSearchResponse(kb_source="milvus", items=items, total=len(items))
        except Exception as exc:  # noqa: BLE001 - 依赖外部服务，按三态口径降级
            logger.warning("知识检索不可用（Milvus/Ollama）: %s", exc)
            return KnowledgeSearchResponse(kb_source="unavailable", items=[], total=0)


# 模块级单例：Milvus/Ollama 连接懒加载复用
knowledge_service = KnowledgeService()
