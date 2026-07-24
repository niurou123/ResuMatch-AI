"""向量存储测试"""
import pytest
import shutil
from pathlib import Path
from src.rag.vector_store import ResumeVectorStore
from src.rag.parser import Document


@pytest.fixture
def vector_store():
    """创建测试用向量存储"""
    test_path = "data/chroma_db_test"
    store = ResumeVectorStore(persist_path=test_path)
    yield store
    # 清理
    try:
        store.client.delete_collection("skills")
        store.client.delete_collection("projects")
        store.client.delete_collection("achievements")
        store.client.delete_collection("education")
    except Exception:
        pass
    if Path(test_path).exists():
        shutil.rmtree(test_path, ignore_errors=True)


@pytest.fixture
def sample_documents():
    """示例文档块"""
    return [
        Document(
            content="技能: Python (类别: programming)",
            metadata={"type": "skill", "name": "Python", "category": "programming"},
            chunk_id="skill_0",
        ),
        Document(
            content="技能: LangGraph (类别: ai)",
            metadata={"type": "skill", "name": "LangGraph", "category": "ai"},
            chunk_id="skill_1",
        ),
        Document(
            content="项目: PaperPilot - 多Agent科研助手\n角色: 核心开发者\n技术栈: LangGraph, Python, ChromaDB",
            metadata={"type": "project", "name": "PaperPilot", "role": "核心开发者"},
            chunk_id="project_0",
        ),
        Document(
            content="项目: ResuMatch AI - Agent面试助手\n技术栈: LangGraph, FastAPI, Streamlit",
            metadata={"type": "project", "name": "ResuMatch AI"},
            chunk_id="project_1",
        ),
        Document(
            content="成果: 引用准确率从35.6%提升至100%",
            metadata={"type": "achievement", "project_name": "PaperPilot"},
            chunk_id="achievement_0",
        ),
        Document(
            content="教育: XX大学 计算机科学与技术 硕士",
            metadata={"type": "education", "school": "XX大学", "degree": "硕士"},
            chunk_id="education_0",
        ),
    ]


class TestResumeVectorStore:
    """向量存储测试套件"""

    def test_init_creates_collections(self, vector_store):
        """测试初始化创建所有集合"""
        for name in ResumeVectorStore.COLLECTIONS:
            count = vector_store.count(name)
            assert count >= 0  # 集合存在且可查询

    def test_index_documents(self, vector_store, sample_documents):
        """测试文档索引"""
        total = vector_store.index_documents(sample_documents)
        assert total == len(sample_documents)

        # 验证各集合的文档数
        assert vector_store.count("skills") == 2
        assert vector_store.count("projects") == 2
        assert vector_store.count("achievements") == 1
        assert vector_store.count("education") == 1

    def test_search_skills(self, vector_store, sample_documents):
        """测试技能检索"""
        vector_store.index_documents(sample_documents)

        results = vector_store.search("Python 编程", "skills", top_k=2)
        assert len(results) > 0
        assert any("Python" in r["content"] for r in results)

    def test_search_projects(self, vector_store, sample_documents):
        """测试项目检索"""
        vector_store.index_documents(sample_documents)

        results = vector_store.search("LangGraph 工作流", "projects", top_k=2)
        assert len(results) > 0
        # PaperPilot 应该排在前面（与 LangGraph 更相关）
        assert any("PaperPilot" in r["content"] for r in results)

    def test_search_with_metadata_filter(self, vector_store, sample_documents):
        """测试带 metadata 过滤的检索"""
        vector_store.index_documents(sample_documents)

        # 只检索 programming 类别的技能
        results = vector_store.search(
            "编程", "skills", top_k=5,
            where={"category": "programming"}
        )
        for r in results:
            assert r.get("metadata", {}).get("category") == "programming"

    def test_search_all_async(self, vector_store, sample_documents):
        """测试并行检索所有集合"""
        vector_store.index_documents(sample_documents)

        import asyncio
        async def run():
            return await vector_store.search_all("Python LangGraph", top_k=3)

        results = asyncio.run(run())

        assert isinstance(results, dict)
        # 至少有一个集合返回了结果
        assert any(len(v) > 0 for v in results.values())

    def test_search_empty_collection(self, vector_store):
        """测试空集合检索"""
        results = vector_store.search("Python", "skills")
        assert results == []

    def test_get_collection_info(self, vector_store, sample_documents):
        """测试获取集合统计"""
        vector_store.index_documents(sample_documents)

        info = vector_store.get_collection_info()
        assert info["skills"] == 2
        assert info["projects"] == 2
        assert isinstance(info, dict)

    def test_reset(self, vector_store, sample_documents):
        """测试重置集合"""
        vector_store.index_documents(sample_documents)
        assert vector_store.count("skills") > 0

        vector_store.reset()
        assert vector_store.count("skills") == 0
        assert vector_store.count("projects") == 0
