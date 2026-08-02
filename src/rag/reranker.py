"""Cross-Encoder 重排器 - 精排初检结果"""
from typing import List, Dict, Any, Optional
import threading
import numpy as np
from src.config import settings


class CrossEncoderReranker:
    """
    交叉编码器重排器

    流程：Bi-Encoder 初检 top-K → Cross-Encoder 精排 top-N

    Bi-Encoder (bge-small-zh): 编码时查询和文档独立，速度快但精度有限
    Cross-Encoder (bge-reranker-base): 同时编码查询和文档对，捕捉 token 级交互，精度更高

    额外延迟 < 500ms（批量推理）
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.RERANKER_MODEL
        self._model = None
        self._lock = threading.Lock()  # 防止并发重复加载

    @property
    def model(self):
        """延迟加载 Cross-Encoder 模型"""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import CrossEncoder
                        self._model = CrossEncoder(self.model_name)
                    except ImportError:
                        raise ImportError(
                            "需要安装 sentence-transformers: pip install sentence-transformers"
                        )
        return self._model

    def rerank(
        self, query: str, candidates: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        对候选结果重排序

        Args:
            query: 原始查询文本
            candidates: 初检结果列表，每个结果需含 "content" 字段
            top_k: 精排后保留数量，默认使用 RETRIEVAL_TOP_K

        Returns:
            重排后的结果列表，附加 "rerank_score" 字段
        """
        top_k = top_k or settings.RERANK_TOP_K

        if not candidates:
            return []

        if len(candidates) <= top_k:
            # 候选数量不足，直接返回
            for c in candidates:
                c["rerank_score"] = c.get("score", 0.0)
            return candidates

        # 构建 (query, document) 对
        pairs = [(query, c.get("content", "")) for c in candidates]

        # Cross-Encoder 预测相关性分数
        scores = self.model.predict(pairs, show_progress_bar=False)

        # 添加重排分数
        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = float(scores[i]) if i < len(scores) else 0.0

        # 按重排分数降序排序
        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        return ranked[:top_k]

    def rerank_multi_query(
        self, queries: List[str], candidates: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        多查询重排：取多个查询与文档对的最高分

        适用于查询扩展场景（原始查询 + 扩展词）
        """
        top_k = top_k or settings.RERANK_TOP_K

        if not candidates:
            return []

        # 对每个查询分别计算分数，取最大值
        all_scores = np.zeros(len(candidates))

        for query in queries:
            pairs = [(query, c.get("content", "")) for c in candidates]
            scores = self.model.predict(pairs, show_progress_bar=False)
            all_scores = np.maximum(all_scores, scores)

        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = float(all_scores[i])

        ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]


# 全局重排器实例
_reranker: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    """获取全局重排器实例"""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker
