"""结构化简历档案 / 项目库持久化 — JSON 读写

用途：上传简历时把解析出的结构化 profile（含 projects/skills/achievements/education）
落盘到 data/profile.json，供项目-JD 匹配引擎等后续模块读取。

相比从 ChromaDB 读被切碎的 child chunk，这里是可靠的完整结构化数据源。
"""
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List

from src.config import settings

PROFILE_PATH = Path(settings.CHROMA_DB_PATH).parent / "profile.json" if hasattr(settings, "CHROMA_DB_PATH") else Path("data/profile.json")


class ProfileStore:
    """简历档案 JSON 存储"""

    @staticmethod
    def _path() -> Path:
        # 优先 data/ 目录下的 profile.json，兼容旧配置
        return Path("data") / "profile.json"

    @classmethod
    def save(cls, profile: Dict[str, Any]) -> None:
        """原子写入 profile JSON（先写临时文件再改名，避免写坏）"""
        path = cls._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # 临时文件写入同一目录，确保 rename 原子性
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """读取 profile，文件不存在/损坏时返回 {}"""
        path = cls._path()
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def get_projects(cls) -> List[Dict[str, Any]]:
        """返回结构化项目库列表（过滤掉无名的空项目）"""
        profile = cls.load()
        projects = profile.get("projects", [])
        return [p for p in projects if isinstance(p, dict) and p.get("name")]

    @classmethod
    def clear(cls) -> None:
        """删除 profile 文件"""
        path = cls._path()
        if path.exists():
            path.unlink()
