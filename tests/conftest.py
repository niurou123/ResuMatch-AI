"""测试配置和共享 fixtures"""
import pytest
import os
import sys
from pathlib import Path

# 添加 src 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key")
os.environ.setdefault("CHROMA_DB_PATH", "data/chroma_db_test")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture
def sample_resume_text():
    """示例简历文本"""
    return """
张三

联系方式: zhangsan@example.com | 13800138000

## 技能
Python, Java, FastAPI, React
LangGraph, LangChain, RAG
Docker, Kubernetes, Git
MySQL, Redis, ChromaDB, FAISS
PyTorch, Transformers, LoRA

## 项目经验

### PaperPilot - 多Agent科研助手 (2026.06 - 2026.07)
角色: 核心开发者
技术栈: LangGraph, Python, DeepSeek API, ChromaDB, bge-small-zh
描述: 面向研究场景的AI科研助手，输入研究问题后自动拆解子查询、多源并行检索，交叉分析后生成带引用的结构化Markdown研究报告。
关键成果:
- 设计4节点LangGraph工作流+条件修订边，支持N轮修订回环
- 规则化Planner跳过LLM调用，规划阶段2min→0s
- 检索节点5合并为4，延迟15-40s→3-10s
- Prompt工程修复引用准确性，准确率35.6%→100%
- RAG管道支持PDF/TXT/MD/DOCX解析，top-5命中率100%

### ResuMatch AI - Agent面试助手 (2026.07)
角色: 独立开发
技术栈: LangGraph, FastAPI, ChromaDB, Streamlit, DeepSeek API
描述: 基于多Agent协作的AI面试助手，蒸馏个人简历，向量化优势，智能生成个性化面试回答。
关键成果:
- 5节点LangGraph工作流：ProfileAnalyzer→QuestionRouter→ExperienceRetriever→STARWriter→QualityReviewer
- HyDE+Self-Query+Cross-Encoder增强检索管道
- 三层会话记忆+LLM摘要压缩

## 教育背景
XX大学 计算机科学与技术 硕士 2024-2026
XX大学 软件工程 学士 2020-2024
"""


@pytest.fixture
def sample_parsed_resume():
    """示例解析后的结构化简历"""
    from src.rag.parser import ParsedResume
    return ParsedResume(
        name="张三",
        email="zhangsan@example.com",
        phone="13800138000",
        skills=[
            {"name": "Python", "category": "programming"},
            {"name": "Java", "category": "programming"},
            {"name": "FastAPI", "category": "framework"},
            {"name": "LangGraph", "category": "ai"},
            {"name": "ChromaDB", "category": "database"},
            {"name": "Docker", "category": "devops"},
        ],
        projects=[
            {
                "name": "PaperPilot",
                "role": "核心开发者",
                "tech_stack": ["LangGraph", "Python", "DeepSeek API", "ChromaDB"],
                "description": "多Agent科研助手",
                "key_result": "引用准确率35.6%→100%",
            },
            {
                "name": "ResuMatch AI",
                "role": "独立开发",
                "tech_stack": ["LangGraph", "FastAPI", "Streamlit"],
                "description": "Agent面试助手",
                "key_result": "首字延迟<2s",
            },
        ],
        achievements=[
            {"description": "设计4节点LangGraph工作流+条件修订边"},
            {"description": "[PaperPilot] Prompt工程修复引用准确性，准确率35.6%→100%"},
        ],
        education=[
            {"school": "XX大学", "degree": "计算机科学与技术 硕士", "time": "2024-2026"},
        ],
    )
