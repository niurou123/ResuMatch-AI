"""Redis 存储模块 — 会话持久化 + LLM 缓存

用途：
1. 面试对练会话状态持久化（替代内存 dict，服务重启不丢）
2. LLM 回答语义缓存（命中省成本/延迟）

降级策略（关键退路）：
- Redis 不可用（未安装/未启动/连接失败）→ 自动退回内存 dict，功能不受影响
- 符合 CLAUDE.md 退路机制原则：LLM/外部依赖不可用时规则化降级
"""
import hashlib
import json
import threading
from typing import Dict, Any, List, Optional

from src.config import settings

# 全局连接（惰性）
_client = None
_client_lock = threading.Lock()
_available = None  # None=未知, True/False


def _get_client():
    """获取 Redis 客户端（惰性 + 缓存可用性判断）"""
    global _client, _available
    if _available is False:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:
            return _client
        try:
            import redis
            kwargs = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "decode_responses": True,
                "protocol": 2,  # 兼容 Redis 5.x（tporadowski 移植版不支持 HELLO 命令）
            }
            if settings.REDIS_PASSWORD:
                kwargs["password"] = settings.REDIS_PASSWORD
            _client = redis.Redis(**kwargs)
            _client.ping()  # 验证连接
            _available = True
            return _client
        except Exception:
            _available = False
            _client = None
            return None


def is_available() -> bool:
    """Redis 是否可用"""
    return _get_client() is not None


class RedisSessionStore:
    """面试会话持久化存储（Redis，不可用时降级内存 dict）"""

    # 降级用内存存储（进程内）
    _fallback: Dict[str, Any] = {}
    _lock = threading.Lock()

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    @classmethod
    def get(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """读取会话。Redis 优先，降级内存。"""
        client = _get_client()
        if client:
            try:
                raw = client.get(cls._key(session_id))
                return json.loads(raw) if raw else None
            except Exception:
                pass  # 降级内存
        with cls._lock:
            return cls._fallback.get(session_id)

    @classmethod
    def set(cls, session_id: str, data: Dict[str, Any], ttl: int = None) -> None:
        """写入会话（带 TTL 过期）"""
        ttl = ttl or settings.REDIS_TTL_SESSION
        client = _get_client()
        if client:
            try:
                client.set(cls._key(session_id), json.dumps(data, ensure_ascii=False), ex=ttl)
                return
            except Exception:
                pass  # 降级内存
        with cls._lock:
            cls._fallback[session_id] = data

    @classmethod
    def delete(cls, session_id: str) -> None:
        """删除会话"""
        client = _get_client()
        if client:
            try:
                client.delete(cls._key(session_id))
            except Exception:
                pass
        with cls._lock:
            cls._fallback.pop(session_id, None)

    @classmethod
    def clear_all(cls) -> None:
        """清空所有会话（测试用）"""
        client = _get_client()
        if client:
            try:
                for k in client.scan_iter("session:*"):
                    client.delete(k)
            except Exception:
                pass
        with cls._lock:
            cls._fallback.clear()


class LLMCache:
    """LLM 回答缓存（精确哈希 + 语义近邻）

    语义缓存（semantic caching）：对 query 做 embedding，在已缓存的
    query 向量中找余弦相似度 ≥ 阈值的最近邻——"技能栈是什么"和
    "你会哪些技术"视为同一问题命中同一答案。此前只有 sha256 精确
    匹配，query 差一个字就 miss，"语义缓存"名不副实。

    实现：query 向量存 Redis（内存降级时存进程内存），向量数量为
    缓存条目数（几十到几百），近邻搜索用 numpy 暴力算——O(n·d)，
    百级规模 <1ms，无需专门 ANN 索引。
    """

    # 降级用内存缓存
    _fallback: Dict[str, str] = {}

    # 语义缓存索引：prefix → {payload_key: query_text}
    # （存 query 文本而非向量：嵌入器延迟计算，避免模块级依赖 rag 层）
    _sem_index: Dict[str, Dict[str, str]] = {}

    # 语义命中阈值（余弦相似度）——过高形同虚设，过低误命中不同问题
    SEMANTIC_THRESHOLD: float = 0.92

    @staticmethod
    def _key(prefix: str, payload: str) -> str:
        h = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"cache:{prefix}:{h}"

    # ===== 精确缓存 =====

    @classmethod
    def get(cls, prefix: str, payload: str) -> Optional[str]:
        """读取缓存（精确 key）"""
        if not settings.REDIS_CACHE_ENABLED:
            return None
        client = _get_client()
        if client:
            try:
                return client.get(cls._key(prefix, payload))
            except Exception:
                pass
        return cls._fallback.get(cls._key(prefix, payload))

    @classmethod
    def set(cls, prefix: str, payload: str, value: str, ttl: int = None) -> None:
        """写入缓存（TTL）；payload 同时登记进语义索引"""
        if not settings.REDIS_CACHE_ENABLED:
            return
        ttl = ttl or settings.REDIS_TTL_CACHE
        key = cls._key(prefix, payload)
        client = _get_client()
        if client:
            try:
                client.set(key, value, ex=ttl)
                # 语义索引同步登记（value 不进索引，按 key 取值）
                cls._register_semantic(prefix, key, payload)
                return
            except Exception:
                pass
        cls._fallback[key] = value
        cls._register_semantic(prefix, key, payload)

    # ===== 语义缓存 =====

    @classmethod
    def _register_semantic(cls, prefix: str, key: str, payload: str) -> None:
        """把 payload 登记进语义索引（取 payload 前半段作为代表 query）"""
        try:
            # payload 形如 "question|project|skills...|..."——首段就是问题文本
            query_text = payload.split("|")[0].strip()
            if len(query_text) >= 6:  # 过短的 query 语义区分度不足，不进索引
                cls._sem_index.setdefault(prefix, {})[key] = query_text
        except Exception:
            pass

    @classmethod
    def get_semantic(cls, prefix: str, query: str) -> Optional[str]:
        """语义读取：query 与已缓存问题做向量近邻匹配，≥阈值返回缓存答案。

        失败即返回 None（调用方走精确 get 或重新生成）——语义缓存是
        增益路径，不能成为故障点（错误隔离）。
        """
        if not settings.REDIS_CACHE_ENABLED:
            return None
        query = (query or "").strip()
        if len(query) < 6:
            return None

        index = cls._sem_index.get(prefix, {})
        if not index:
            return None

        try:
            import numpy as np
            from src.rag.embedder import get_embedder

            candidates = list(index.items())
            texts = [q for _, q in candidates]
            # 编码归一化后点积即余弦相似度
            q_vec = get_embedder().encode_single(query)
            cand_vecs = get_embedder().encode(texts)
            sims = cand_vecs @ q_vec

            best = int(np.argmax(sims))
            if float(sims[best]) >= cls.SEMANTIC_THRESHOLD:
                key = candidates[best][0]
                # 取出对应缓存值（Redis 优先，降级内存）
                client = _get_client()
                if client:
                    try:
                        val = client.get(key)
                        if val:
                            return val
                    except Exception:
                        pass
                return cls._fallback.get(key)
        except Exception:
            return None
        return None

    @classmethod
    def flush_prefix(cls, prefix: str) -> None:
        """失效某前缀的缓存（如数据更新后）；语义索引同步清空"""
        client = _get_client()
        if client:
            try:
                for k in client.scan_iter(f"cache:{prefix}:*"):
                    client.delete(k)
            except Exception:
                pass
        with RedisSessionStore._lock:
            cls._fallback = {
                k: v for k, v in cls._fallback.items() if not k.startswith(f"cache:{prefix}:")
            }
        cls._sem_index.pop(prefix, None)


# 全局实例
session_store = RedisSessionStore()
llm_cache = LLMCache()
