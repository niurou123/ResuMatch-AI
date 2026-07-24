"""嵌入服务 - BAAI/bge-small-zh 中文嵌入模型"""
import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer
from src.config import settings


class Embedder:
    """文本嵌入服务"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model: SentenceTransformer = None

    @property
    def model(self) -> SentenceTransformer:
        """延迟加载模型"""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        """嵌入向量维度"""
        return settings.EMBEDDING_DIM

    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        编码文本为向量

        Args:
            texts: 单个文本或文本列表
            batch_size: 批量编码大小

        Returns:
            numpy 数组，形状 (n, dim)
        """
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 归一化，用于余弦相似度
        )

        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        """编码单个文本"""
        return self.encode(text)[0]

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """批量编码文本"""
        return self.encode(texts, batch_size=batch_size)


# 全局嵌入器实例（延迟初始化）
_embedder: Embedder = None


def get_embedder() -> Embedder:
    """获取全局嵌入器实例"""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
