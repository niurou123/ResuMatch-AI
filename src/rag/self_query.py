"""Self-Query 自查询检索 - LLM 将自然语言翻译为结构化 ChromaDB 查询"""
import json
from typing import Dict, Any, List, Optional
from src.core.llm_client import get_client, Message


SELF_QUERY_SYSTEM_PROMPT = """你是一个查询构建助手。将用户的面试问题转换为结构化的 ChromaDB 检索查询。

## 可用集合（collections）:
- skills: 技能信息 (metadata: name, category, level)
- projects: 项目经验 (metadata: name, role, tech_stack, key_result)
- achievements: 成果/成就 (metadata: description, project_name)
- education: 教育背景 (metadata: school, degree, major)

## 输出 JSON 格式:
{
    "query": "优化后的检索关键词",
    "target_collections": ["projects", "achievements"],
    "filters": {
        "collection_name": {"field": "value"}
    },
    "expand_terms": ["相关扩展词1", "相关扩展词2"]
}

## 规则:
1. query: 从问题中提取核心检索意图，去除冗余词
2. target_collections: 选择最相关的 1-3 个集合
3. filters: 可选，如果问题明确提到了项目名/技术/公司等，添加过滤条件
4. expand_terms: 对关键术语的同义词、上下位词扩展

只返回 JSON，不要其他文字。"""


class SelfQueryRetriever:
    """LLM 自动构建结构化查询"""

    def __init__(self):
        self.client = get_client()

    async def build_query(self, question: str) -> Dict[str, Any]:
        """
        将自然语言问题翻译为结构化查询

        示例:
        "你在 PaperPilot 项目中怎么用 LangGraph 的？"
        → {
            "query": "LangGraph 工作流设计 多Agent协作",
            "target_collections": ["projects", "achievements"],
            "filters": {"projects": {"name": "PaperPilot"}},
            "expand_terms": ["LangGraph", "StateGraph", "条件边", "Agent工作流"]
        }
        """
        messages = [
            Message(role="system", content=SELF_QUERY_SYSTEM_PROMPT),
            Message(role="user", content=question),
        ]

        try:
            raw = await self.client.chat_sync(messages, temperature=0.1)
            result = json.loads(raw)
            return self._validate(result)
        except (json.JSONDecodeError, ValueError):
            # 降级：不做结构化过滤，直接原始查询
            return {
                "query": question,
                "target_collections": ["skills", "projects", "achievements"],
                "filters": {},
                "expand_terms": [],
            }

    def _validate(self, result: Dict) -> Dict:
        """验证并补全查询结构"""
        valid_collections = {"skills", "projects", "achievements", "education"}

        if "query" not in result:
            result["query"] = ""
        if "target_collections" not in result:
            result["target_collections"] = ["skills", "projects", "achievements"]
        if "filters" not in result:
            result["filters"] = {}
        if "expand_terms" not in result:
            result["expand_terms"] = []

        # 过滤无效集合
        result["target_collections"] = [
            c for c in result["target_collections"] if c in valid_collections
        ]
        if not result["target_collections"]:
            result["target_collections"] = ["skills", "projects", "achievements"]

        return result

    def build_simple(self, question: str) -> Dict[str, Any]:
        """同步简化版（无 LLM 调用，规则化）"""
        import re

        # 检测项目名
        project_patterns = [
            r'(?:在|关于|介绍|讲).{0,10}([A-Za-z一-鿿]{2,20})(?:项目|系统|平台|助手|工具)',
            r'([A-Z][a-z]+(?:[A-Z][a-z]+)+)',  # CamelCase 项目名
        ]

        filters = {}
        target_collections = ["skills", "projects", "achievements"]

        for pattern in project_patterns:
            match = re.search(pattern, question)
            if match:
                proj_name = match.group(1)
                filters["projects"] = {"name": proj_name}
                target_collections = ["projects", "achievements"]
                break

        # 检测问题类型 → 调整集合优先级
        if any(kw in question for kw in ["技能", "技术", "会", "用过", "熟悉"]):
            target_collections = ["skills", "projects"]
        elif any(kw in question for kw in ["成果", "成绩", "成就", "获奖"]):
            target_collections = ["achievements", "projects"]
        elif any(kw in question for kw in ["学历", "学校", "专业", "毕业"]):
            target_collections = ["education"]

        # 扩展词（基于关键词规则）
        expand_terms = []
        tech_keywords = {
            "向量数据库": ["FAISS", "ChromaDB", "Milvus"],
            "大模型": ["LLM", "GPT", "DeepSeek", "RAG"],
            "工作流": ["LangGraph", "DAG", "Pipeline"],
            "微调": ["LoRA", "QLoRA", "Fine-tuning"],
            "后端": ["FastAPI", "Django", "Flask"],
            "前端": ["React", "Vue", "Streamlit"],
        }
        for keyword, expansions in tech_keywords.items():
            if keyword in question:
                expand_terms.extend(expansions)

        return {
            "query": question,
            "target_collections": target_collections,
            "filters": filters,
            "expand_terms": expand_terms,
        }
