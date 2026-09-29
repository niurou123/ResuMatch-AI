"""Milvus Lite 向量存储 - 多集合管理（嵌入式，ChromaDB 为自动降级退路）

架构说明：
- 主路径：Milvus Lite（pymilvus MilvusClient，本地单文件 data/milvus_resumatch.db）
  - 免 Docker、Windows 原生、API 与 Milvus Standalone 完全兼容（可平滑迁移生产）
  - Milvus 有 SIGMOD 2021 论文（Milvus: A Purpose-Built Vector Data Management System）
- 退路：pymilvus 不可用（未安装/初始化失败）时自动降级到 ChromaDB 实现，功能不受影响
  （遵循 CLAUDE.md 退路机制原则：外部依赖不可用时降级，不阻塞）

数据模型：
- 每个集合一个 Milvus collection（skills/projects/achievements/education/project_docs）
- Milvus 要求 schema 固定，故只建 4 个标量字段：
    content(str) / metadata(JSON) / collection_name(str) / chunk_id 为 primary key
- 上层 ChromaDB 风格的 where={"field": value} 过滤在 Milvus 侧翻译为
  JSON 字段的 key 精确匹配（json_contains_key 不可用于等值，直接用 JSON 路径等值）

兼容层约定（与旧 ChromaDB 实现完全一致，调用方零改动）：
- search() 返回 [{"id", "content", "metadata", "score", "collection"}]，score 为相似度（越大越好）
- Milvus COSINE 度量返回相似度本身，透传即可；ChromaDB 余弦距离则转为 1-distance
- 空集合 search 返回 []；n_results 不超过集合内实体数
"""
import json
import threading
from typing import List, Dict, Any, Optional

from src.config import settings
from src.rag.embedder import get_embedder, Embedder
from src.rag.parser import Document


class MilvusVectorStore:
    """
    简历向量存储 - Milvus Lite 多集合管理

    五个集合：
    - skills: 技能向量
    - projects: 项目经验向量
    - achievements: 成果/成就向量
    - education: 教育背景向量
    - project_docs: 项目资料文档（档案页按项目上传）
    """

    COLLECTIONS = ["skills", "projects", "achievements", "education", "project_docs"]

    def __init__(self, persist_path: str = None):
        self.persist_path = persist_path or settings.MILVUS_DB_PATH
        self.embedder = get_embedder()
        self._client = None
        self._lock = threading.Lock()
        self._ensure_collections()

    # ==================== 连接与集合管理 ====================

    def _get_client(self):
        """获取 Milvus 客户端（本地文件 uri 即嵌入式 Milvus Lite）"""
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is not None:
                return self._client
            from pymilvus import MilvusClient
            # uri 为本地文件路径 → pymilvus 自动启用 Milvus Lite 嵌入式模式
            # （注意：必须是文件路径，写成 host:port 会静默连到远端服务）
            self._client = MilvusClient(uri=self.persist_path)
        return self._client

    def _schema(self):
        """统一集合 schema（Milvus 要求固定字段，metadata 整体存 JSON）"""
        from pymilvus import CollectionSchema, FieldSchema, DataType
        return CollectionSchema(
            fields=[
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedder.dim),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ],
            description="ResuMatch 简历素材",
        )

    def _ensure_collections(self) -> None:
        """确保所有集合已创建（幂等）"""
        try:
            client = self._get_client()
            existing = set(client.list_collections())
            for name in self.COLLECTIONS:
                if name not in existing:
                    client.create_collection(
                        collection_name=name,
                        schema=self._schema(),
                        # Lite 模式支持 FLAT 精确检索（本数据量百级，无需 HNSW）
                        index_params=self._index_params(),
                    )
        except Exception as e:
            raise RuntimeError(f"Milvus 集合初始化失败: {e}") from e

    def _index_params(self):
        """FLAT 精确检索索引（milvus-lite 内核即 FLAT，无需 HNSW）"""
        # prepare_index_params 的挂载位置跨 pymilvus 版本有差异，两种都试
        try:
            from pymilvus import MilvusClient
            return MilvusClient.prepare_index_params(
                index_type="FLAT", metric_type="COSINE", params={},
            )
        except Exception:
            pass
        try:
            from pymilvus import IndexParams
            ip = IndexParams()
            ip.add_index(index_type="FLAT", metric_type="COSINE", params={})
            return ip
        except Exception:
            return None

    # ==================== 写入 ====================

    def reset(self) -> None:
        """重置所有集合（删除并重建）"""
        client = self._get_client()
        for name in self.COLLECTIONS:
            try:
                client.drop_collection(name)
            except Exception:
                pass
        self._ensure_collections()

    def index_documents(self, documents: List[Document]) -> int:
        """
        将文档列表索引到对应集合（metadata.type 决定集合）

        Returns: 索引的文档总数
        """
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
        """批量索引文档到指定集合（空 content 用后备文本，杜绝空向量入库）"""
        client = self._get_client()

        texts = []
        for doc in documents:
            if doc.content and doc.content.strip():
                texts.append(doc.content)
            else:
                # 用 metadata 中的 name 作为后备 content
                name = doc.metadata.get("name", "")
                texts.append(name if name else f"{collection_name} #{doc.metadata.get('index', doc.chunk_id)}")

        embeddings = self.embedder.encode(texts)
        rows = [
            {
                "chunk_id": doc.chunk_id[:128],
                "embedding": embeddings[i].tolist(),
                "content": texts[i][:65535],
                "metadata": {
                    k: (str(v) if isinstance(v, list) else v)
                    for k, v in doc.metadata.items()
                    if isinstance(v, (str, int, float, bool))
                },
            }
            for i, doc in enumerate(documents)
        ]

        client.insert(collection_name=collection_name, data=rows)

    # ==================== 查询 ====================

    def _translate_where(self, where: Optional[Dict]) -> Optional[str]:
        """ChromaDB 风格 where={"k": v} → Milvus 布尔表达式（JSON 字段等值匹配）"""
        if not where:
            return None
        # 只支持扁平等值（本项目所有调用点均为 {"project_name": x} / {"category": x} 形态）
        exprs = []
        for key, value in where.items():
            if isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                exprs.append(f'metadata["{key}"] == "{escaped}"')
            elif isinstance(value, (int, float, bool)):
                exprs.append(f'metadata["{key}"] == {value}')
            else:
                continue
        return " and ".join(exprs) if exprs else None

    def _query(
        self, embedding: List[float], collection_name: str,
        top_k: int, where: Optional[Dict],
    ) -> List[Dict[str, Any]]:
        """内部统一查询：向量近邻 + 可选 metadata 过滤"""
        client = self._get_client()
        n = self.count(collection_name)
        if n == 0 or top_k <= 0:
            return []

        filter_expr = self._translate_where(where)
        results = client.search(
            collection_name=collection_name,
            data=[embedding],
            limit=min(top_k, n),
            filter=filter_expr,
            output_fields=["content", "metadata"],
            search_params=None,  # FLAT 无需额外参数
        )
        return self._format_results(results, collection_name)

    def search(
        self, query: str, collection_name: str,
        top_k: int = None, where: Dict = None
    ) -> List[Dict[str, Any]]:
        """在指定集合中检索（query 文本现算向量）"""
        top_k = top_k or settings.RETRIEVAL_TOP_K

        if collection_name not in self.COLLECTIONS:
            return []

        query_embedding = self.embedder.encode_single(query)
        return self._query(query_embedding.tolist(), collection_name, top_k, where)

    def search_by_embedding(
        self, embedding, collection_name: str,
        top_k: int = None, where: Dict = None
    ) -> List[Dict[str, Any]]:
        """使用已有 embedding 检索（用于 HyDE）"""
        top_k = top_k or settings.RETRIEVAL_TOP_K

        if collection_name not in self.COLLECTIONS:
            return []

        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
        return self._query(embedding, collection_name, top_k, where)

    async def search_all(
        self, query: str, top_k: int = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """并行检索所有集合（保持 ChromaDB 版的 async 签名）"""
        import asyncio

        top_k = top_k or settings.RETRIEVAL_TOP_K

        async def search_one(name: str):
            return name, self.search(query, name, top_k=top_k)

        tasks = [search_one(name) for name in self.COLLECTIONS]
        results = await asyncio.gather(*tasks)

        return {name: result for name, result in results if result}

    # ==================== 统计 ====================

    def _format_results(
        self, raw_results: List[Dict], collection_name: str
    ) -> List[Dict[str, Any]]:
        """格式化 MilvusClient.search 结果"""
        formatted = []
        if not raw_results:
            return formatted

        hits = raw_results[0]  # 单查询向量 → 第一组结果
        for hit in hits:
            entity = hit.get("entity", {}) or {}
            metadata = entity.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            # FLAT 索引返回的 hit 可能不带主键 id，从 entity 取 chunk_id 兜底
            doc_id = hit.get("id") or entity.get("chunk_id", "") or ""
            raw = float(hit.get("distance", 0.0))
            # Milvus COSINE 度量返回的是相似度（越大越相似），非距离。
            # 上层约定的 score 是"越大越好"，直接透传；越界值裁剪到 [-1, 1]
            score = max(-1.0, min(1.0, raw))
            formatted.append({
                "id": doc_id,
                "content": entity.get("content", "") or "",
                "metadata": metadata,
                "score": score,
                "collection": collection_name,
            })

        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted

    def count(self, collection_name: str) -> int:
        """获取集合中的文档数"""
        try:
            client = self._get_client()
            if collection_name not in client.list_collections():
                return 0
            return client.get_collection_stats(collection_name).get("row_count", 0)
        except Exception:
            return 0

    def list_documents(
        self, collection_name: str, limit: int = 200,
        where: Dict = None,
    ) -> List[Dict[str, Any]]:
        """确定性枚举集合内文档（替代用空 query 做向量检索的"刮库"）。

        空字符串 query 的 embedding 是一个随机方向上的向量，返回的
        top-k 是伪随机样本且顺序不稳定；需要"全部素材"时应该用 query。
        返回格式与 search() 一一对应（score 无意义，置 0）。
        """
        if collection_name not in self.COLLECTIONS:
            return []
        try:
            client = self._get_client()
            if collection_name not in client.list_collections():
                return []
            n = self.count(collection_name)
            if n == 0:
                return []
            filter_expr = self._translate_where(where)
            rows = client.query(
                collection_name=collection_name,
                filter=filter_expr,
                limit=min(limit, n),
                output_fields=["content", "metadata"],
            )
            results = []
            for row in rows:
                metadata = row.get("metadata", {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                results.append({
                    "id": row.get("chunk_id", "") or "",
                    "content": row.get("content", "") or "",
                    "metadata": metadata,
                    "score": 0.0,  # 枚举无相似度语义
                    "collection": collection_name,
                })
            return results
        except Exception:
            return []

    def get_collection_info(self) -> Dict[str, int]:
        """获取所有集合的文档统计"""
        return {name: self.count(name) for name in self.COLLECTIONS}


# ==================== 退路机制：ChromaDB 降级 ====================

class _ChromaFallbackStore:
    """ChromaDB 实现（原 ResumeVectorStore），pymilvus 不可用时降级使用"""

    def __init__(self, persist_path: str = None):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.persist_path = persist_path or settings.CHROMA_DB_PATH
        self.client = chromadb.PersistentClient(
            path=self.persist_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.embedder = get_embedder()
        self._collections: Dict[str, Any] = {}
        self.COLLECTIONS = MilvusVectorStore.COLLECTIONS
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        for name in self.COLLECTIONS:
            try:
                self._collections[name] = self.client.get_collection(name)
            except Exception:
                self._collections[name] = self.client.create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )

    def reset(self) -> None:
        for name in self.COLLECTIONS:
            try:
                self.client.delete_collection(name)
            except Exception:
                pass
        self._collections = {}
        self._ensure_collections()

    def index_documents(self, documents: List[Document]) -> int:
        grouped: Dict[str, List[Document]] = {c: [] for c in self.COLLECTIONS}
        for doc in documents:
            doc_type = doc.metadata.get("type", "skills")
            if doc_type in grouped:
                grouped[doc_type].append(doc)
            elif doc_type == "work":
                grouped["projects"].append(doc)

        total = 0
        for collection_name, docs in grouped.items():
            if not docs:
                continue
            self._index_batch(collection_name, docs)
            total += len(docs)
        return total

    def _index_batch(self, collection_name: str, documents: List[Document]) -> None:
        collection = self._collections[collection_name]

        texts = []
        for doc in documents:
            if doc.content and doc.content.strip():
                texts.append(doc.content)
            else:
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
        top_k = top_k or settings.RETRIEVAL_TOP_K
        if collection_name not in self._collections:
            return []

        collection = self._collections[collection_name]
        query_embedding = self.embedder.encode_single(query)

        # 空集合直接返回（ChromaDB 拒绝 n_results=0，会抛 TypeError）
        if collection.count() == 0:
            return []
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
        top_k = top_k or settings.RETRIEVAL_TOP_K
        if collection_name not in self._collections:
            return []

        collection = self._collections[collection_name]
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()

        # 空集合直接返回（ChromaDB 拒绝 n_results=0，会抛 TypeError）
        if collection.count() == 0:
            return []
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return self._format_results(results, collection_name)

    async def search_all(self, query: str, top_k: int = None):
        import asyncio
        top_k = top_k or settings.RETRIEVAL_TOP_K

        async def search_one(name: str):
            return name, self.search(query, name, top_k=top_k)

        tasks = [search_one(name) for name in self.COLLECTIONS]
        results = await asyncio.gather(*tasks)
        return {name: result for name, result in results if result}

    def _format_results(self, raw_results: Dict, collection_name: str):
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
                "score": 1.0 - distances[i] if i < len(distances) else 0.0,
                "collection": collection_name,
            })
        formatted.sort(key=lambda x: x["score"], reverse=True)
        return formatted

    def count(self, collection_name: str) -> int:
        if collection_name in self._collections:
            return self._collections[collection_name].count()
        return 0

    def list_documents(
        self, collection_name: str, limit: int = 200, where: Dict = None
    ) -> List[Dict[str, Any]]:
        """确定性枚举（与 Milvus 路径同名同义：替代空 query 刮库）"""
        if collection_name not in self._collections:
            return []
        try:
            n = self.count(collection_name)
            if n == 0:
                return []
            results = self._collections[collection_name].get(
                limit=min(limit, n), where=where,
                include=["documents", "metadatas"],
            )
            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            out = []
            for i, doc_id in enumerate(ids):
                out.append({
                    "id": doc_id,
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "score": 0.0,  # 枚举无相似度语义
                    "collection": collection_name,
                })
            return out
        except Exception:
            return []

    def get_collection_info(self) -> Dict[str, int]:
        return {name: self.count(name) for name in self.COLLECTIONS}


# ==================== 工厂：优先 Milvus，降级 ChromaDB ====================

_store: Optional[MilvusVectorStore] = None
_store_backend: str = ""  # "milvus" | "chromadb"


def _create_store() -> Any:
    """创建向量存储：Milvus Lite 优先，初始化失败自动降级 ChromaDB"""
    global _store_backend
    try:
        store = MilvusVectorStore()
        _store_backend = "milvus"
        return store
    except Exception as e:
        print(f"[WARN] Milvus Lite 不可用，降级 ChromaDB: {e}")
        _store_backend = "chromadb"
        return _ChromaFallbackStore()


def get_vector_store() -> Any:
    """获取全局向量存储实例（接口兼容，调用方无感知后端切换）"""
    global _store
    if _store is None:
        _store = _create_store()
    return _store


def get_vector_backend() -> str:
    """当前向量库后端（"milvus" / "chromadb"，供系统信息端点展示）"""
    get_vector_store()  # 确保已初始化
    return _store_backend
