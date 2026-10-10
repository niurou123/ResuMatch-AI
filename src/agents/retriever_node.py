"""
多Agent并行检索 - 3路独立Agent + 并行编排（v2 落实版）

Agent 1: keyword_agent - 关键词精确匹配 (Self-Query LLM 结构化过滤，规则版为退路)
Agent 2: semantic_agent - 语义向量检索 (HyDE + Bi-Encoder + Cross-Encoder精排 + Multi-Query)
Agent 3: knowledge_graph_agent - 知识图谱推理 (Skill Graph类别展开)

落实项（相对 v1）：
- Planner 的 retrieval_top_k 真正传入检索（此前写入 state 无人读取）
- decomposed_queries 真正参与检索：多查询召回 + rerank_multi_query 融合（RAG Fusion）
- Self-Query 用 LLM 版 build_query（规则版 build_simple 为降级退路）
- 同步核心（ChromaDB/Milvus 查询、embedding 编码、torch 推理）包
  asyncio.to_thread —— asyncio.gather 对同步段无效，此前"并行"只是协程级
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


def _effective_top_k(state: AgentState) -> int:
    """读取 Planner 决策的检索深度（动态调度的实际接线点）。

    Planner 按 question_type + difficulty 计算 retrieval_top_k（3-20），
    各检索 Agent 用它作为单路召回上限。此前该值只写进 state 无人消费，
    前端 DAG 展示的"Top-K"与实际检索量脱节。
    """
    try:
        top_k = state.get("planner_decisions", {}).get("retrieval_top_k")
        if top_k:
            return max(3, min(30, int(top_k)))
    except (TypeError, ValueError):
        pass
    return 10  # 兜底默认


# ============ Agent 1: 关键词检索 ============
async def keyword_agent(state: AgentState) -> AgentState:
    """
    Agent 1: 关键词专家
    策略：Self-Query 结构化查询 → 向量库 metadata 过滤
    优势：精确匹配技术栈、项目名、技能名

    Self-Query 主路径走 LLM（build_query，将自然语言翻译为
    结构化过滤 + 查询词 + 扩展词）；LLM 不可用/解析失败时
    降级到规则版 build_simple（错误隔离 + 退路机制）。
    """
    query = state.get("query", "")
    if not query.strip(): return state

    try:
        self_query = SelfQueryRetriever()
        # 上游已构建结构化查询（评测预注入 / 复用 Router 结果）则直接采用，
        # 不再调 LLM——Self-Query 是「可选增强」不是必经步骤
        structured = state.get("self_query_filter")
        if not isinstance(structured, dict) or not structured.get("query"):
            try:
                structured = await asyncio.wait_for(
                    self_query.build_query(query), timeout=15.0
                )
            except Exception:
                # 退路：LLM Self-Query 失败（超时/格式错/网络）→ 规则化结构查询
                structured = self_query.build_simple(query)
        state["self_query_filter"] = structured

        top_k = _effective_top_k(state)
        enhanced_query = query
        expand_terms = structured.get("expand_terms", [])
        if expand_terms:
            enhanced_query = f"{query} {' '.join(expand_terms[:3])}"

        vs = get_vector_store()
        # 检索核心是同步阻塞（Milvus/Chroma 查询 + embedding 编码），放线程池
        def _run():
            results = []
            for coll in structured.get("target_collections", ["skills","projects","achievements"]):
                where = structured.get("filters", {}).get(coll)
                r = vs.search(enhanced_query, coll, top_k=top_k, where=where)
                results.extend(r)
            return results

        results = await asyncio.to_thread(_run)
        state["keyword_results"] = _deduplicate(results)
    except Exception:
        state["keyword_results"] = []

    return state


# ============ Agent 2: 语义检索 ============
async def semantic_agent(state: AgentState) -> AgentState:
    """
    Agent 2: 语义专家
    策略：HyDE 假设文档 + Bi-Encoder 向量检索 + Cross-Encoder 精排
    增强：Multi-Query（decomposed_queries 真正参与检索，每个子查询独立召回，
    Cross-Encoder 对多查询取每文档最大分 —— RAG Fusion 思路）
    优势：理解隐含语义（"最大挑战"→简历中的"优化"相关内容）
    """
    query = state.get("query", "")
    user_profile = state.get("user_profile", {})
    if not query.strip(): return state

    try:
        top_k = _effective_top_k(state)
        hyde = HyDERetriever()
        hypothetical = ""
        # 快速模式（面试对练）：跳过 HyDE 的 LLM 调用（~9s），直接用 query 检索，优先速度
        is_fast = state.get("planner_decisions", {}).get("skip_review", False)
        if not is_fast:
            try:
                summary = ""
                if user_profile.get("name"):
                    skills = [s.get("name","") for s in user_profile.get("skills",[])[:8]]
                    summary = f"姓名:{user_profile['name']}, 技能:{', '.join(skills)}"
                hypothetical = await hyde._generate_hypothetical(query, summary)
            except Exception:
                pass
        state["hypothetical_answer"] = hypothetical

        # Multi-Query：Router 拆解的子查询（含原始查询）逐个检索
        # 原始查询放最前（权重自然最高：Cross-Encoder 取 max，原查询必算）
        sub_queries = [query]
        for dq in state.get("decomposed_queries", [])[:3]:
            dq = (dq or "").strip()
            if dq and dq != query:
                sub_queries.append(dq)

        vs = get_vector_store()
        def _run():
            all_results = []
            # project_docs：档案页按项目上传的资料文档，与简历素材一同参与检索
            for q in sub_queries:
                for coll in ["skills","projects","achievements","education","project_docs"]:
                    r = vs.search(q, coll, top_k=top_k)
                    all_results.extend(r)

            # HyDE 检索（用假设文档的向量，通常比原始问题更接近答案文本分布）
            if hypothetical:
                from src.rag.embedder import get_embedder
                emb = get_embedder().encode_single(hypothetical)
                for coll in ["skills","projects","achievements"]:
                    hr = vs.search_by_embedding(emb, coll, top_k=8)
                    all_results.extend(hr)

            all_results = _deduplicate(all_results)

            # Cross-Encoder 精排：多查询取每文档最高分（RAG Fusion 语义）
            if len(all_results) > 10:
                try:
                    reranker = get_reranker()
                    if len(sub_queries) > 1:
                        all_results = reranker.rerank_multi_query(sub_queries, all_results, top_k=10)
                    else:
                        all_results = reranker.rerank(query, all_results, top_k=10)
                except Exception:
                    pass
            return all_results

        all_results = await asyncio.to_thread(_run)
        state["semantic_results"] = all_results[:10]
    except Exception:
        state["semantic_results"] = []

    return state


# ============ Agent 3: 知识图谱推理 ============
async def knowledge_graph_agent(state: AgentState) -> AgentState:
    """
    Agent 3: 知识图谱专家
    策略：Skill Graph 类别推理 + 关联技能展开
    优势：理解"向量数据库"→[FAISS, ChromaDB, Milvus]→[PaperPilot项目]
    """
    query = state.get("query", "")
    if not query.strip(): return state

    try:
        top_k = _effective_top_k(state)
        graph = SkillGraph()
        expansions = await asyncio.to_thread(graph.expand_query, query)
        state["knowledge_expansions"] = expansions

        vs = get_vector_store()
        def _run():
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
            return graph_results

        graph_results = await asyncio.to_thread(_run)
        state["graph_results"] = _deduplicate(graph_results)[:10]
    except Exception:
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

    # 过滤占位/空内容素材（如 "achievements #0"、"skills #3" 等空 content 回退占位）
    # 这些素材对回答无价值，混入会污染 writer 输入导致空回答/低分
    def _is_placeholder(r: dict) -> bool:
        content = (r.get("content") or "").strip()
        if not content:
            return True
        # 匹配 "{collection} #{index}" 占位格式（vector_store 空 content 回退）
        import re as _re
        if _re.match(r'^(skills|projects|achievements|education)\s*#\d+$', content):
            return True
        return False

    keyword = [r for r in keyword if not _is_placeholder(r)]
    semantic = [r for r in semantic if not _is_placeholder(r)]
    graph = [r for r in graph if not _is_placeholder(r)]

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

    # 项目定向召回：若问题提到具体项目，优先把该项目素材顶上来（防止跨项目混入）
    all_results = _boost_targeted_project(state, all_results)

    # 按投票数+相似度综合排序
    all_results.sort(key=lambda x: (x.get("vote_count", 0), x.get("score", 0)), reverse=True)
    state["reranked_context"] = all_results[:8]

    # 按集合分类
    state["retrieved_skills"] = [r for r in all_results if r.get("collection") == "skills"][:5]
    state["retrieved_projects"] = [r for r in all_results if r.get("collection") == "projects"][:5]
    state["retrieved_achievements"] = [r for r in all_results if r.get("collection") == "achievements"][:5]
    state["retrieved_education"] = [r for r in all_results if r.get("collection") == "education"][:3]
    state["retrieved_project_docs"] = [r for r in all_results if r.get("collection") == "project_docs"][:3]

    return state


def _boost_targeted_project(state: AgentState, results: list) -> list:
    """
    项目定向召回增强：
    从问题中检测是否提到具体项目（按项目关键词表），若命中，
    提升该项目素材的 vote_count/score，并确保至少召回若干条该项目素材。
    防止"问A项目却混入B项目素材"的张冠李戴。
    """
    query = state.get("query", "")
    if not query:
        return results

    # 项目关键词 → 项目别名（用于匹配素材归属）
    project_keywords = [
        ("ResuMatch", ["ResuMatch", "网申面试", "面试助手", "AI面试"]),
        ("视觉康复", ["视觉康复", "随访", "医疗", "康复"]),
        ("PaperPilot", ["PaperPilot", "论文", "科研助手"]),
        ("MLLM", ["MLLM", "多模态摘要", "图神经网络"]),
    ]

    # 问题命中哪个项目
    targeted = None
    for proj_name, aliases in project_keywords:
        if any(a in query for a in aliases):
            targeted = proj_name
            break
    if not targeted:
        return results

    # 找出属于该项目的素材（source_text / name / content 含项目别名）
    target_aliases = dict(project_keywords).get(targeted, [targeted])
    project_results = []
    for r in results:
        md = r.get("metadata", {}) or {}
        # project_docs 用 metadata.project_name 标注归属，其余集合靠 name/source_text/content
        haystack = f"{md.get('source_text','')} {md.get('name','')} {md.get('project_name','')} {r.get('content','')}"
        if any(a in haystack for a in target_aliases):
            project_results.append(r)

    # 项目素材提权：优先保证进入最终上下文
    boosted_ids = {r.get("id") for r in project_results}
    for r in results:
        if r.get("id") in boosted_ids:
            r["vote_count"] = r.get("vote_count", 1) + 2  # 项目命中大幅提权
            r["score"] = r.get("score", 0) + 0.3
            r["project_boosted"] = True

    # 非目标项目的素材降权（防止张冠李戴：明确提到A项目时，弱化B项目素材）
    non_target_ids = []
    for r in results:
        if r.get("id") not in boosted_ids and r.get("collection") in ("projects", "achievements", "project_docs"):
            md = r.get("metadata", {}) or {}
            haystack = f"{md.get('source_text','')} {md.get('name','')} {md.get('project_name','')} {r.get('content','')}"
            # 属于"已知项目"（能识别出归属）但非目标项目 → 降权
            is_known_other_project = False
            for other_proj, other_aliases in project_keywords:
                if other_proj == targeted:
                    continue
                if any(a in haystack for a in other_aliases):
                    is_known_other_project = True
                    break
            if is_known_other_project:
                r["vote_count"] = max(0, r.get("vote_count", 1) - 3)
                r["score"] = r.get("score", 0) - 0.5
                r["project_filtered"] = True
                non_target_ids.append(r.get("id"))

    # 强约束：明确提到目标项目时，把能识别出"属于其他项目"的素材从上下文中剔除，
    # 避免 writer 仍读到跨项目素材而混写（降权排序不足以阻止 LLM 读取）
    if non_target_ids:
        non_target_ids = set(non_target_ids)
        results = [r for r in results if r.get("id") not in non_target_ids]

    # 若项目素材过少（<2条），尝试从向量库补充召回该项目的成果/项目素材
    if len(project_results) < 2:
        try:
            from src.rag.vector_store import get_vector_store
            vs = get_vector_store()
            extra = []
            for coll in ["projects", "achievements", "project_docs"]:
                for alias in target_aliases:
                    r = vs.search(alias, coll, top_k=5)
                    for item in r:
                        md = item.get("metadata", {}) or {}
                        haystack = f"{md.get('source_text','')} {md.get('name','')} {md.get('project_name','')} {item.get('content','')}"
                        if any(a in haystack for a in target_aliases):
                            item["sources"] = ["project_targeted"]
                            item["vote_count"] = 3
                            item["score"] = 0.9
                            item["project_boosted"] = True
                            extra.append(item)
            # 去重并入队
            seen_ids = {r.get("id") for r in results}
            for item in extra:
                if item.get("id") not in seen_ids:
                    seen_ids.add(item.get("id"))
                    results.append(item)
        except Exception:
            pass

    return results


# ============ 并行编排节点 ============
async def parallel_retrieval_node(state: AgentState) -> AgentState:
    """
    并行编排节点：使用 asyncio.gather 真正并行调度3个检索Agent

    优势：
    - 3个Agent完全并发执行，总耗时 = max(单Agent耗时) 而非 sum
      （Agent 内部的同步阻塞段已包 asyncio.to_thread，事件循环不再被卡）
    - Planner决策控制哪些Agent被激活、检索深度（retrieval_top_k 已接线）
    - 错误隔离：单个Agent失败不影响其他
    """
    decisions = state.get("planner_decisions", {})
    active_retrievers = decisions.get("active_retrievers", ["keyword", "semantic", "graph"])
    query = state.get("query", "")

    if not query.strip():
        return state

    # 构建 Agent 函数及其名称（按 Planner 决策）[仅构建，不创建协程以避免未 await 的警告]
    agent_refs = []
    if "keyword" in active_retrievers:
        agent_refs.append(("keyword", keyword_agent))
    if "semantic" in active_retrievers:
        agent_refs.append(("semantic", semantic_agent))
    if "graph" in active_retrievers:
        agent_refs.append(("graph", knowledge_graph_agent))

    if not agent_refs:
        return state

    # 真正并行执行！(带 per-agent 计时)
    async def timed_agent_wrapper(name, agent_fn, s):
        t0 = time.time()
        try:
            await agent_fn(s)
            elapsed = time.time() - t0
            return name, "success", round(elapsed * 1000, 1), None
        except Exception as e:
            elapsed = time.time() - t0
            return name, "failed", round(elapsed * 1000, 1), str(e)[:100]

    timed_tasks = [timed_agent_wrapper(n, fn, state) for n, fn in agent_refs]
    task_names = [n for n, _ in agent_refs]
    start_time = time.time()
    agent_results = await asyncio.gather(*timed_tasks, return_exceptions=True)
    total_elapsed = time.time() - start_time

    agent_timing = {}
    for r in agent_results:
        if isinstance(r, Exception):
            continue
        name, status, elapsed_ms, err = r
        agent_timing[name] = {"status": status, "elapsed_ms": elapsed_ms, "error": err}

    # 记录融合统计
    total_docs = (
        len(state.get("keyword_results", [])) +
        len(state.get("semantic_results", [])) +
        len(state.get("graph_results", []))
    )

    state["fusion_stats"] = {
        "active_agents": task_names,
        "parallel_elapsed_ms": round(total_elapsed * 1000, 1),
        "agent_timing": agent_timing,
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
