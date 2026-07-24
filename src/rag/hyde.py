"""HyDE (Hypothetical Document Embeddings) - 假设文档嵌入检索"""
from typing import List, Dict, Any
from src.core.llm_client import get_client, Message
from src.rag.embedder import get_embedder
from src.rag.vector_store import get_vector_store


HYDE_SYSTEM_PROMPT = """你是一个面试回答模拟器。基于用户的简历背景，用一段话回答给定的面试问题。

注意：
1. 假装你是简历的主人（候选人本人）
2. 用第一人称回答
3. 包含具体的项目名、技术名、数字指标
4. 控制在 200 字以内
5. 只输出回答内容，不要加任何前缀说明"""


class HyDERetriever:
    """
    假设文档嵌入检索器

    原理：
    1. LLM 生成假设的理想回答
    2. 用假设回答的向量去做实际检索
    3. 这比直接用问题检索更精准（桥接语义鸿沟）

    适用场景：
    - 问题"你遇到的最大挑战" vs 简历"将延迟从15s优化到3s"
    - 问题"你的优势是什么" vs 简历"熟悉LangGraph多Agent协作"
    """

    def __init__(self):
        self.client = get_client()
        self.embedder = get_embedder()
        self.vector_store = get_vector_store()

    async def retrieve(
        self, question: str, user_profile: Dict[str, Any],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        HyDE 检索流程：
        1. 生成假设回答
        2. 用假设回答向量检索所有集合
        3. 返回合并结果
        """
        # Step 1: 生成假设回答
        profile_summary = self._build_profile_summary(user_profile)
        hypothetical = await self._generate_hypothetical(question, profile_summary)

        # Step 2: 用假设回答的向量检索
        hypo_embedding = self.embedder.encode_single(hypothetical)

        all_results = []
        for collection in ["skills", "projects", "achievements", "education"]:
            results = self.vector_store.search_by_embedding(
                hypo_embedding, collection, top_k=top_k
            )
            all_results.extend(results)

        # 按相似度排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    async def _generate_hypothetical(
        self, question: str, profile_summary: str
    ) -> str:
        """LLM 生成假设回答"""
        messages = [
            Message(role="system", content=HYDE_SYSTEM_PROMPT),
            Message(role="user", content=f"简历背景:\n{profile_summary}\n\n问题: {question}"),
        ]
        return await self.client.chat_sync(messages, temperature=0.5)

    def _build_profile_summary(self, profile: Dict[str, Any]) -> str:
        """构建简历摘要（用于 HyDE prompt）"""
        parts = []

        if profile.get("name"):
            parts.append(f"姓名: {profile['name']}")

        skills = profile.get("skills", [])
        if skills:
            skill_names = [s.get("name", "") for s in skills[:10]]
            parts.append(f"技能: {', '.join(skill_names)}")

        projects = profile.get("projects", [])
        if projects:
            parts.append("项目经验:")
            for proj in projects[:5]:
                name = proj.get("name", "")
                techs = proj.get("tech_stack", [])
                result = proj.get("key_result", "")
                tech_str = f" (技术栈: {', '.join(techs)})" if techs else ""
                result_str = f" - 成果: {result}" if result else ""
                parts.append(f"  - {name}{tech_str}{result_str}")

        achievements = profile.get("achievements", [])
        if achievements:
            ach_items = [a.get("description", "") for a in achievements[:5] if a.get("description")]
            if ach_items:
                parts.append(f"主要成果: {'; '.join(ach_items)}")

        return "\n".join(parts)
