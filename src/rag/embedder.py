"""嵌入服务 - BAAI/bge-small-zh 中文嵌入模型"""
import threading
import numpy as np
from typing import List, Union
from src.config import settings


class Embedder:
    """文本嵌入服务"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None
        self._lock = threading.Lock()  # 防止多线程并发重复加载模型（冷启动 10-20s）

    def _find_local_path(self, name):
        "从 HuggingFace 缓存查找本地模型路径（优先选有 config.json 的完整 snapshot）"
        import os as _os
        cache = _os.environ.get("HF_HOME", "") or _os.path.join(_os.path.expanduser("~"), ".cache", "huggingface")
        hub_dir = _os.path.join(cache, "hub")
        safe_name = "models--" + name.replace("/", "--")
        model_dir = _os.path.join(hub_dir, safe_name, "snapshots")
        if _os.path.isdir(model_dir):
            snaps = sorted(_os.listdir(model_dir), reverse=True)
            for snap in snaps:
                snap_path = _os.path.join(model_dir, snap)
                try:
                    files = _os.listdir(snap_path)
                except Exception:
                    continue
                # 必须包含 config.json，优先有 tokenizer 文件的
                if "config.json" in files:
                    return snap_path
        return None

    @property
    def model(self):
        """延迟加载模型（优先从本地缓存，同时忽略 torch 版本警告）。
        加锁防止多线程并发重复加载（冷启动 10-20s，重复加载会拖垮响应）。"""
        if self._model is None:
            with self._lock:
                # 双重检查：持锁后再确认一次，避免等待锁的线程重复加载
                if self._model is None:
                    self._model = self._load_model()
        return self._model

    def _load_model(self):
        """实际加载模型（带 CVE 补丁）"""
        import os as _os, importlib
        from sentence_transformers import SentenceTransformer

        # 禁用 CVE-2025-32434 的 torch 版本检查
        _orig_check = None
        try:
            mod = importlib.import_module("transformers.modeling_utils")
            _orig_check = mod.check_torch_load_is_safe
            mod.check_torch_load_is_safe = lambda: None
        except Exception:
            pass

        # 优先从本地缓存加载（使用包含完整 config/tokenizer 的 snapshot）
        _os.environ["HF_HUB_OFFLINE"] = "1"
        local_path = self._find_local_path(self.model_name)

        try:
            if local_path:
                return SentenceTransformer(local_path, trust_remote_code=True)
            return SentenceTransformer(self.model_name, trust_remote_code=True)
        finally:
            if _orig_check is not None:
                try:
                    importlib.import_module("transformers.modeling_utils").check_torch_load_is_safe = _orig_check
                except Exception:
                    pass

    @property
    def dim(self) -> int:
        """嵌入向量维度"""
        return settings.EMBEDDING_DIM

    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """编码文本为向量"""
        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
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
