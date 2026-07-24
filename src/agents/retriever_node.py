"""Node 3: ExperienceRetriever - 增强检索管道"""
import asyncio
from typing import Dict, Any, List
from src.agents.state import AgentState
from src.rag.self_query import SelfQueryRetriever
from src.rag.hyde import HyDERetriever
from src.rag.knowledge_graph import SkillGraph

# 延迟导入 chromadb 相关模块
def _get_vector_store():
    from src.rag.vector_store import get_vector_store
    return get_vector_store()

def _get_reranker():
    from src.rag.reranker import get_reranker
    return get_reranker()


async def experience_retriever_node(state: AgentState) -> AgentState:
    """
    Node 3: ExperienceRetriever

    增强检索管道：
    3a. Skill Graph 查询扩展
    3b. Self-Query 结构化过滤
    3c. HyDE 假设文档生成 + 检索
    3d. 并行检索 4 源 (Bi-Encoder top-20)
    3e. Cross-Encoder 精排 (top-20 → top-5)
    """
    query = state.get("query", "")
    user_profile = state.get("user_profile", {})
    knowledge_expansions = state.get("knowledge_expansions", [])

    if not query.strip():
        return state

    try:
        vector_store = _get_vector_store()

        # ===== 3a. Skill Graph 查询扩展 =====
        skill_graph = SkillGraph()
        expansions = skill_graph.expand_query(query)
        state["knowledge_expansions"] = expansions

        # ===== 3b. Self-Query 结构化过滤 =====
        self_query = SelfQueryRetriever()
        structured = self_query.build_simple(query)
        state["self_query_filter"] = structured

        target_collections = structured.get("target_collections", ResumeVectorStore_COLLECTIONS)
        chroma_filters = structured.get("filters", {})

        # ===== 3c. HyDE 假设文档生成 =====
        hyde = HyDERetriever()
        try:
            hypothetical = await hyde._generate_hypothetical(
                query,
                hyde._build_profile_summary(user_profile)
            )
            state["hypothetical_answer"] = hypothetical
        except Exception:
            hypothetical = None

        # ===== 3d. 并行检索所有目标集合 =====
        async def search_collection(name: str) -> tuple:
            # 使用 Self-Query 的过滤条件
            where_filter = chroma_filters.get(name)

            # 常规检索
            results = vector_store.search(query, name, top_k=20, where=where_filter)

            # 如果有 HyDE 假设回答，也用它检索
            if hypothetical:
                from src.rag.embedder import get_embedder
                embedder = get_embedder()
                hypo_emb = embedder.encode_single(hypothetical)
                hyde_results = vector_store.search_by_embedding(
                    hypo_emb, name, top_k=10, where=where_filter
                )
                # 合并去重
                seen_ids = {r["id"] for r in results}
                for hr in hyde_results:
                    if hr["id"] not in seen_ids:
                        results.append(hr)

            # 扩展词检索
            for exp_term in expansions[:3]:
                exp_results = vector_store.search(exp_term, name, top_k=5, where=where_filter)
                seen_ids = {r["id"] for r in results}
                for er in exp_results:
                    if er["id"] not in seen_ids:
                        results.append(er)

            return name, results

        # 并行执行所有检索
        tasks = [search_collection(name) for name in target_collections]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        merged_skills = []
        merged_projects = []
        merged_achievements = []
        merged_education = []

        for result in all_results:
            if isinstance(result, Exception):
                continue
            name, items = result
            if name == "skills":
                merged_skills = items
            elif name == "projects":
                merged_projects = items
            elif name == "achievements":
                merged_achievements = items
            elif name == "education":
                merged_education = items

        # 合并所有候选（用于精排）
        all_candidates = (
            merged_skills + merged_projects +
            merged_achievements + merged_education
        )

        # 去重 + 按分数排序
        seen = set()
        unique_candidates = []
        for c in sorted(all_candidates, key=lambda x: x["score"], reverse=True):
            if c["id"] not in seen:
                seen.add(c["id"])
                unique_candidates.append(c)

        state["retrieved_skills"] = merged_skills[:10]
        state["retrieved_projects"] = merged_projects[:10]
        state["retrieved_achievements"] = merged_achievements[:10]
        state["retrieved_education"] = merged_education[:5]

        # ===== 3e. Cross-Encoder 精排 =====
        if len(unique_candidates) > 5:
            try:
                reranker = _get_reranker()
                # 构建多查询（原始查询 + 扩展词）
                all_queries = [query]
                if hypothetical:
                    all_queries.append(hypothetical)
                all_queries.extend(expansions[:2])

                reranked = reranker.rerank_multi_query(
                    all_queries, unique_candidates, top_k=5
                )
                state["reranked_context"] = reranked
            except Exception:
                # Cross-Encoder 不可用时，直接取 top-5
                state["reranked_context"] = unique_candidates[:5]
        else:
            state["reranked_context"] = unique_candidates[:5]

    except Exception as e:
        state["error"] = f"检索失败: {str(e)}"

    return state


# 4 个默认集合
ResumeVectorStore_COLLECTIONS = ["skills", "projects", "achievements", "education"]
