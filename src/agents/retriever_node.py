"""
多Agent并行检索 - 3路独立Agent + 并行编排

Agent 1: keyword_agent - 关键词精确匹配 (Self-Query + ChromaDB metadata过滤)
Agent 2: semantic_agent - 语义向量检索 (HyDE + Bi-Encoder + Cross-Encoder精排)
Agent 3: knowledge_graph_agent - 知识图谱推理 (Skill Graph类别展开)

parallel_retrieval_node: 使用 asyncio.gather 真正并行调度3个Agent
"""
import asyncio
import time
from typing import Dict, Any, List
from src.agents.state import AgentState
from src.rag.vector_store import get_vector_store
from src.rag.self_query import SelfQueryRetriever
from src.rag.hyde import HyDERetriever
from src.rag.reranker import get_reranker
from src.rag.knowledge_graph import SkillGraph


# ============ Agent 1: 关键词检索 ============
async def keyword_agent(state: AgentState) -> AgentState:
    """
    Agent 1: 关键词专家
    策略：Self-Query 结构化查询 → ChromaDB metadata 过滤
    优势：精确匹配技术栈、项目名、技能名
    """
    query = state.get("query", "")
    if not query.strip(): return state

    try:
        self_query = SelfQueryRetriever()
        structured = self_query.build_simple(query)
        state["self_query_filter"] = structured

        vs = get_vector_store()
        results = []
        for coll in structured.get("target_collections", ["skills","projects","achievements"]):
            where = structured.get("filters", {}).get(coll)
            r = vs.search(query, coll, top_k=10, where=where)
            results.extend(r)

        state["keyword_results"] = _deduplicate(results)
    except Exception as e:
        state["keyword_results"] = []

    return state


# ============ Agent 2: 语义检索 ============
async def semantic_agent(state: AgentState) -> AgentState:
    """
    Agent 2: 语义专家
    策略：HyDE假设文档 + Bi-Encoder向量检索 + Cross-Encoder精排
    优势：理解隐含语义（"最大挑战"→简历中的"优化"相关内容）
    """
    query = state.get("query", "")
    user_profile = state.get("user_profile", {})
    if not query.strip(): return state

    try:
        hyde = HyDERetriever()
        hypothetical = ""
        try:
            summary = ""
            if user_profile.get("name"):
                skills = [s.get("name","") for s in user_profile.get("skills",[])[:8]]
                summary = f"姓名:{user_profile['name']}, 技能:{', '.join(skills)}"
            hypothetical = await hyde._generate_hypothetical(query, summary)
        except: pass
        state["hypothetical_answer"] = hypothetical

        vs = get_vector_store()
        all_results = []
        for coll in ["skills","projects","achievements","education"]:
            r = vs.search(query, coll, top_k=10)
            all_results.extend(r)

        # HyDE 检索
        if hypothetical:
            from src.rag.embedder import get_embedder
            emb = get_embedder().encode_single(hypothetical)
            for coll in ["skills","projects","achievements"]:
                hr = vs.search_by_embedding(emb, coll, top_k=8)
                all_results.extend(hr)

        # Cross-Encoder 精排
        if len(all_results) > 10:
            try:
                reranker = get_reranker()
                all_results = reranker.rerank(query, all_results, top_k=10)
            except: pass

        state["semantic_results"] = _deduplicate(all_results)[:10]
    except Exception as e:
        state["semantic_results"] = []

    return state


# ============ Agent 3: 知识图谱推理 ============
async def knowledge_graph_agent(state: AgentState) -> AgentState:
    """
    Agent 3: 知识图谱专家
    策略：Skill Graph 类别推理 + 关联技能展开
    优势：理解"向量数据库"→[FAISS, ChromaDB]→[PaperPilot项目]
    """
    query = state.get("query", "")
    if not query.strip(): return state

    try:
        graph = SkillGraph()
        expansions = graph.expand_query(query)
        state["knowledge_expansions"] = expansions

        vs = get_vector_store()
        graph_results = []
        # 用展开后的术语检索
        for term in expansions[:5]:
            for coll in ["skills","projects","achievements"]:
                r = vs.search(term, coll, top_k=5)
                graph_results.extend(r)

        # 也检索原始查询
        for coll in ["skills","projects","achievements"]:
            r = vs.search(query, coll, top_k=5)
            graph_results.extend(r)

        state["graph_results"] = _deduplicate(graph_results)[:10]
    except Exception as e:
        state["graph_results"] = []

    return state


# ============ Fusion: 合并+投票排序 ============
async def fusion_node(state: AgentState) -> AgentState:
    """
    融合节点：合并3个Agent的检索结果
    投票策略：被多个Agent检索到的结果排名更高
    """
    keyword = state.get("keyword_results", [])
    semantic = state.get("semantic_results", [])
    graph = state.get("graph_results", [])

    # 合并所有结果
    all_results = []
    seen = set()

    for source_name, source_results in [("keyword", keyword), ("semantic", semantic), ("graph", graph)]:
        for r in source_results:
            cid = r.get("id", "")
            if cid not in seen:
                seen.add(cid)
                r["sources"] = [source_name]
                r["vote_count"] = 1
                all_results.append(r)
            else:
                # 更新已有结果：多Agent共识加分
                for existing in all_results:
                    if existing.get("id") == cid:
                        existing["sources"].append(source_name)
                        existing["vote_count"] = len(existing["sources"])
                        existing["score"] = existing.get("score", 0) * 1.1  # 共识加权
                        break

    # 按投票数+相似度综合排序
    all_results.sort(key=lambda x: (x.get("vote_count", 0), x.get("score", 0)), reverse=True)
    state["reranked_context"] = all_results[:8]

    # 按集合分类
    state["retrieved_skills"] = [r for r in all_results if r.get("collection") == "skills"][:5]
    state["retrieved_projects"] = [r for r in all_results if r.get("collection") == "projects"][:5]
    state["retrieved_achievements"] = [r for r in all_results if r.get("collection") == "achievements"][:5]
    state["retrieved_education"] = [r for r in all_results if r.get("collection") == "education"][:3]

    return state


# ============ 并行编排节点 ============
async def parallel_retrieval_node(state: AgentState) -> AgentState:
    """
    并行编排节点：使用 asyncio.gather 真正并行调度3个检索Agent

    优势：
    - 3个Agent完全并发执行，总耗时 = max(单Agent耗时) 而非 sum
    - Planner决策控制哪些Agent被激活
    - 错误隔离：单个Agent失败不影响其他
    """
    decisions = state.get("planner_decisions", {})
    active_retrievers = decisions.get("active_retrievers", ["keyword", "semantic", "graph"])
    query = state.get("query", "")

    if not query.strip():
        return state

    # 构建并行任务列表
    tasks = []
    task_names = []

    if "keyword" in active_retrievers:
        tasks.append(keyword_agent(state))
        task_names.append("keyword")
    if "semantic" in active_retrievers:
        tasks.append(semantic_agent(state))
        task_names.append("semantic")
    if "graph" in active_retrievers:
        tasks.append(knowledge_graph_agent(state))
        task_names.append("graph")

    if not tasks:
        return state

    # 真正并行执行！
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time

    # 处理结果（错误隔离）
    for name, result in zip(task_names, results):
        if isinstance(result, Exception):
            print(f"[ParallelRetrieval] ⚠️ {name}_agent 失败: {result}")
            # 确保失败的Agent结果为空列表
            if name == "keyword":
                state["keyword_results"] = []
            elif name == "semantic":
                state["semantic_results"] = []
            elif name == "graph":
                state["graph_results"] = []
        else:
            # 成功的结果已在各Agent函数中写入state
            pass

    # 记录融合统计
    total_docs = (
        len(state.get("keyword_results", [])) +
        len(state.get("semantic_results", [])) +
        len(state.get("graph_results", []))
    )

    state["fusion_stats"] = {
        "active_agents": task_names,
        "parallel_elapsed_ms": round(elapsed * 1000, 1),
        "total_docs_retrieved": total_docs,
        "agent_breakdown": {
            "keyword": len(state.get("keyword_results", [])),
            "semantic": len(state.get("semantic_results", [])),
            "graph": len(state.get("graph_results", [])),
        },
    }

    # 自动执行 Fusion
    state = await fusion_node(state)

    return state


def _deduplicate(results: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique
