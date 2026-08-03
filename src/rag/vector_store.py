"""ChromaDB 向量存储 - 多集合管理"""
import asyncio
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from src.config import settings
from src.rag.embedder import get_embedder, Embedder
from src.rag.parser import Document


class ResumeVectorStore:
    """
    简历向量存储 - ChromaDB 多集合管理

    四个集合：
    - skills: 技能向量
    - projects: 项目经验向量
    - achievements: 成果/成就向量
    - education: 教育背景向量
    """

    COLLECTIONS = ["skills", "projects", "achievements", "education", "project_docs"]

    def __init__(self, persist_path: str = None):
        self.persist_path = persist_path or settings.CHROMA_DB_PATH
        self.client = chromadb.PersistentClient(
            path=self.persist_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.embedder = get_embedder()
        self._collections: Dict[str, Any] = {}
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """确保所有集合已创建"""
        for name in self.COLLECTIONS:
            try:
                self._collections[name] = self.client.get_collection(name)
            except Exception:
                self._collections[name] = self.client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},  # 余弦相似度
                )

    def reset(self) -> None:
        """重置所有集合（删除并重建）"""
        for name in self.COLLECTIONS:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
        self._collections = {}
        self._ensure_collections()

    def index_documents(self, documents: List[Document]) -> int:
        """
        将文档列表索引到对应的 ChromaDB 集合

        Args:
            documents: 文档列表（metadata.type 决定存入哪个集合）

        Returns:
            索引的文档总数
        """
        # 按类型分组
        grouped: Dict[str, List[Document]] = {c: [] for c in self.COLLECTIONS}
        for doc in documents:
            doc_type = doc.metadata.get("type", "skills")
            if doc_type in grouped:
                grouped[doc_type].append(doc)
            elif doc_type == "work":
                grouped["projects"].append(doc)  # 工作经历归入项目集合

        total = 0
        for collection_name, docs in grouped.items():
            if not docs:
                continue
            self._index_batch(collection_name, docs)
            total += len(docs)

        return total

    def _index_batch(self, collection_name: str, documents: List[Document]) -> None:
        """批量索引文档到指定集合"""
        collection = self._collections[collection_name]

        # 确保 content 不为空（否则 ChromaDB 会存储空字符串导致无意义检索）
        texts = []
        for doc in documents:
            if doc.content and doc.content.strip():
                texts.append(doc.content)
            else:
                # 用 metadata 中的 name 作为后备 content
                name = doc.metadata.get("name", "")
                texts.append(name if name else f"{collection_name} #{doc.metadata.get('index', doc.chunk_id)}")

        embeddings = self.embedder.encode(texts)
        ids = [doc.chunk_id for doc in documents]
        metadatas = [
            {k: (str(v) if isinstance(v, list) else v) for k, v in doc.metadata.items()
             if isinstance(v, (str, int, float, bool))}
            for doc in documents
        ]

        collection.add(
            embeddings=embeddings.tolist(),
            documents=texts,
            ids=ids,
            metadatas=metadatas,
        )

    def search(
        self, query: str, collection_name: str,
        top_k: int = None, where: Dict = None
    ) -> List[Dict[str, Any]]:
        """在指定集合中检索"""
        top_k = top_k or settings.RETRIEVAL_TOP_K

        if collection_name not in self._collections:
            return []

        collection = self._collections[collection_name]
        query_embedding = self.embedder.encode_single(query)

        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return self._format_results(results, collection_name)

    def search_by_embedding(
        self, embedding, collection_name: str,
        top_k: int = None, where: Dict = None
    ) -> List[Dict[str, Any]]:
        """使用已有 embedding 检索（用于 HyDE）"""
        top_k = top_k or settings.RETRIEVAL_TOP_K

        if collection_name not in self._collections:
            return []

        collection = self._collections[collection_name]
        # 确保 embedding 是列表格式
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()

        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        return self._format_results(results, collection_name)

    async def search_all(
        self, query: str, top_k: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """并行检索所有集合"""
        top_k = top_k or settings.RETRIEVAL_TOP_K

        async def search_one(name: str):
            return name, self.search(query, name, top_k=top_k)

        tasks = [search_one(name) for name in self.COLLECTIONS]
        results = await asyncio.gather(*tasks)

        return {name: result for name, result in results if result}

    def _format_results(
        self, raw_results: Dict, collection_name: str
    ) -> List[Dict[str, Any]]:
        """格式化 ChromaDB 查询结果"""
        formatted = []
        if not raw_results.get("ids") or not raw_results["ids"][0]:
            return formatted

        ids = raw_results["ids"][0]
        documents = raw_results.get("documents", [[""] * len(ids)])[0]
        metadatas = raw_results.get("metadatas", [[{}] * len(ids)])[0]
        distances = raw_results.get("distances", [[1.0] * len(ids)])[0]

        for i, doc_id in enumerate(ids):
            formatted.append({
                "id": doc_id,
                "content": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "score": 1.0 - distances[i] if i < len(distances) else 0.0,  # 距离转相似度
                "collection": collection_name,
            })

        # 按相似度降序排序
        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted

    def count(self, collection_name: str) -> int:
        """获取集合中的文档数"""
        if collection_name in self._collections:
            return self._collections[collection_name].count()
        return 0

    def get_collection_info(self) -> Dict[str, int]:
        """获取所有集合的文档统计"""
        return {name: self.count(name) for name in self.COLLECTIONS}


# 全局向量存储实例
_store: Optional[ResumeVectorStore] = None


def get_vector_store() -> ResumeVectorStore:
    """获取全局向量存储实例"""
    global _store
    if _store is None:
        _store = ResumeVectorStore()
    return _store
