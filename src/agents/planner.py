"""Node 1: ProfileAnalyzer - 简历解析 + 向量化"""
from typing import Dict, Any
from pathlib import Path
from src.agents.state import AgentState
from src.rag.parser import ResumeParser
from src.rag.chunker import ParentChildChunker
from src.rag.vector_store import get_vector_store
from src.config import settings


# 全局缓存：避免重复解析同一份简历
_profile_cache: Dict[str, Dict[str, Any]] = {}


async def profile_analyzer_node(state: AgentState) -> AgentState:
    """
    Node 1: ProfileAnalyzer

    职责：
    1. 解析简历文件（PDF/DOCX）
    2. 结构化提取信息
    3. 父子分块 + 向量化存入 ChromaDB
    4. 缓存解析结果，避免重复处理

    初始化时运行一次，后续查询直接使用缓存
    """
    # 如果已初始化，跳过
    if state.get("profile_initialized") and state.get("user_profile"):
        return state

    try:
        parser = ResumeParser()
        chunker = ParentChildChunker()
        vector_store = get_vector_store()

        # 查找简历文件
        resume_path = _find_resume_file()
        if not resume_path:
            state["error"] = "未找到简历文件，请先上传简历"
            return state

        # 检查缓存
        cache_key = str(resume_path)
        if cache_key in _profile_cache:
            state["user_profile"] = _profile_cache[cache_key]
            state["profile_initialized"] = True
            return state

        # 解析简历
        parsed = parser.parse(str(resume_path))

        # 转为文档块
        documents = parser.to_documents(parsed)

        # 父子分块
        child_chunks, parent_chunks, parent_map = chunker.chunk_documents(documents)

        # 向量化存入 ChromaDB（用子块检索）
        vector_store.reset()
        total_indexed = vector_store.index_documents(child_chunks)

        # 构建结构化用户画像
        user_profile = {
            "name": parsed.name,
            "email": parsed.email,
            "phone": parsed.phone,
            "skills": parsed.skills,
            "projects": parsed.projects,
            "achievements": parsed.achievements,
            "education": parsed.education,
            "work_experience": parsed.work_experience,
        }

        # 缓存
        _profile_cache[cache_key] = user_profile
        # 存储父块映射（用于检索时返回完整上下文）
        _profile_cache[f"{cache_key}_parents"] = {
            "chunks": parent_chunks,
            "map": parent_map,
        }

        state["user_profile"] = user_profile
        state["profile_initialized"] = True

    except Exception as e:
        state["error"] = f"简历解析失败: {str(e)}"

    return state


def _find_resume_file() -> Path:
    """在 data/resumes/ 目录中查找简历文件"""
    resumes_dir = Path(settings.RESUME_UPLOAD_PATH)
    if not resumes_dir.exists():
        return None

    supported = settings.get_supported_formats()
    for ext in supported:
        files = list(resumes_dir.glob(f"*.{ext}"))
        if files:
            return files[0]  # 返回第一个找到的文件

    return None
