"""ResuMatch AI 全局配置模块"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """应用全局配置"""

    # ===== 应用信息 =====
    APP_NAME: str = "ResuMatch AI"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ===== API 配置 =====
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # ===== DeepSeek API =====
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_TIMEOUT: int = 60

    # ===== ChromaDB 配置 =====
    CHROMA_DB_PATH: str = "data/chroma_db"
    CHROMA_COLLECTIONS: str = "skills,projects,achievements,education"

    # ===== 嵌入模型配置 =====
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh"
    EMBEDDING_DIM: int = 512

    # ===== 检索配置 =====
    RETRIEVAL_TOP_K: int = 20          # 初检召回数
    RERANK_TOP_K: int = 5              # 精排后保留数
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ===== 简历解析配置 =====
    CHUNK_SIZE: int = 3                # 子块句子数
    PARENT_CHUNK_MIN_LENGTH: int = 50  # 父块最小字符数
    SUPPORTED_RESUME_FORMATS: str = "pdf,docx,md,txt"

    # ===== 推理配置 =====
    MAX_NEW_TOKENS: int = 1024
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.95
    TOP_K: int = 50
    REPETITION_PENALTY: float = 1.0

    # ===== 工作流配置 =====
    MAX_REVISION_ROUNDS: int = 3       # 最大修订轮数
    MIN_REVIEW_SCORE: int = 20         # 最低通过分（满分25）
    STREAM_CHUNK_SIZE: int = 50        # 流式传输块大小

    # ===== 会话记忆配置 =====
    SHORT_TERM_MAX_TURNS: int = 10     # 短期记忆轮数
    MEMORY_MAX_TOKENS: int = 4000      # 记忆最大 token 数
    SUMMARY_MAX_CHARS: int = 500       # 摘要最大字符数
    COMPRESSION_THRESHOLD: int = 48000 # 触发压缩的 token 阈值

    # ===== 数据路径 =====
    RESUME_UPLOAD_PATH: str = "data/resumes"

    # ===== 评测配置 =====
    EVALUATION_METRICS: str = "em,bleu,rouge"

    # ===== 日志配置 =====
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs/"

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}

    def get_chroma_collections(self) -> list[str]:
        """获取 ChromaDB 集合列表"""
        return [c.strip() for c in self.CHROMA_COLLECTIONS.split(",")]

    def get_supported_formats(self) -> list[str]:
        """获取支持的简历文件格式"""
        return [f.strip() for f in self.SUPPORTED_RESUME_FORMATS.split(",")]

    def get_evaluation_metrics(self) -> list[str]:
        """获取评测指标列表"""
        return [m.strip() for m in self.EVALUATION_METRICS.split(",")]


# 全局配置实例
settings = Settings()


def ensure_directories() -> None:
    """确保必要的目录存在"""
    dirs = [
        Path(settings.CHROMA_DB_PATH),
        Path(settings.RESUME_UPLOAD_PATH),
        Path(settings.LOG_DIR),
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
