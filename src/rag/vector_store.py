"""向量存储统一入口（兼容层）

主后端：Milvus Lite（src/rag/milvus_store.py，pymilvus 嵌入式）
退路后端：ChromaDB（同样在 milvus_store.py 内，pymilvus 不可用时自动降级）

本模块保持原导入路径 `from src.rag.vector_store import get_vector_store` 不变，
所有 16 处调用点（routes/retriever_node/hyde/project_matcher/tests）零改动。
"""
from src.rag.milvus_store import (
    MilvusVectorStore,
    get_vector_store,
    get_vector_backend,
)

# 兼容旧代码的类型引用（tests 直接用了 ResumeVectorStore.COLLECTIONS）
ResumeVectorStore = MilvusVectorStore

__all__ = [
    "MilvusVectorStore",
    "ResumeVectorStore",
    "get_vector_store",
    "get_vector_backend",
]
