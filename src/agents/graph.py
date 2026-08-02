"""
多Agent协作 LangGraph 工作流 (v3.0 - 真正并行架构)

架构：
  dynamic_planner → question_router → [conditional: retrieve/skip]
                                        ↓
                               parallel_retrieval (asyncio.gather: 3路并行检索)
                                        ↓
                               star_writer (集成Agent间通信)
                                        ↓
                               parallel_review (asyncio.gather: 3路并行评审)
                                        ↓
                               [conditional: revise → writer / accept → END]

真正的并行：
- 检索阶段：keyword/semantic/graph 3个Agent通过 asyncio.gather 并发执行
- 评审阶段：correctness/completeness/advantage 3个Reviewer通过 asyncio.gather 并发执行
- 总延迟从 sum(3个Agent) 降为 max(3个Agent)

Agent间通信：
- Writer生成后主动识别不确定声明 → 向正确性Reviewer咨询
- Review结果多维度反馈 → Writer迭代优化
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agents.state import AgentState, create_initial_state
from src.agents.planner import dynamic_planner_node, get_planner_summary
from src.agents.router import question_router_node
from src.agents.retriever_node import (
    keyword_agent, semantic_agent, knowledge_graph_agent,
    parallel_retrieval_node
)
from src.agents.writer import star_writer_node, star_writer_stream
from src.agents.reviewer import (
    reviewer_correctness, reviewer_completeness, reviewer_advantage,
    parallel_review_node, vote_node
)
from src.config import settings


# ==================== 条件边 ====================

def should_retrieve(state: AgentState) -> str:
    """
    Planner + Router 联合决策

    当 user_profile 中有 indexed_docs 时就执行检索（已上传简历），
    否则按问题类型判断
    """
    qtype = state.get("question_type", "general")
    profile = state.get("user_profile", {})

    # 有 indexed_docs 或 collections → 简历数据可用，执行检索
    if profile.get("indexed_docs") or profile.get("collections"):
        return "retrieve"

    # 项目/技术/行为类问题
    if qtype in ("project_followup", "technical_depth", "behavioral"):
        return "retrieve"

    return "skip"


def should_revise(state: AgentState) -> Literal["revise", "accept"]:
    """
    多数表决决策：是否需要修订？

    基于 vote_node 的结果：
    - needs_revision=True 且 revision_count < MAX_REVISION_ROUNDS → 修订
    - 否则 → 接受
    """
    # 快速模式（跳过评审）：直接接受，不再走修订回环
    if state.get("planner_decisions", {}).get("skip_review"):
        return "accept"

    needs_revision = state.get("needs_revision", False)
    revision_count = state.get("revision_count", 0)

    if needs_revision and revision_count < settings.MAX_REVISION_ROUNDS:
        return "revise"
    return "accept"


def should_review(state: AgentState) -> Literal["review", "skip"]:
    """是否执行并行评审？快速模式（skip_review=True）跳过评审直接完成"""
    if state.get("planner_decisions", {}).get("skip_review"):
        return "skip"
    return "review"


# ==================== 工作流构建 ====================

def build_graph() -> StateGraph:
    """
    构建真正的多Agent并行工作流：

    Planner (动态调度)
      ↓
    Router (问题分类+拆解)
      ↓
    [条件: retrieve?]
      ├─ retrieve → ParallelRetrieval (3Agent并行+自动Fusion)
      └─ skip ────────────────────────────────┐
                                              ↓
    Writer (STAR生成+Agent通信+自我修正)
      ↓
    ParallelReview (3Reviewer并行+自动投票)
      ↓
    [条件: revise?]
      ├─ revise → Writer (带聚合反馈重新生成)
      └─ accept → END
    """
    workflow = StateGraph(AgentState)

    # ===== 注册节点 =====
    workflow.add_node("planner", dynamic_planner_node)
    workflow.add_node("router", question_router_node)
    workflow.add_node("parallel_retrieval", parallel_retrieval_node)
    workflow.add_node("writer", star_writer_node)
    workflow.add_node("parallel_review", parallel_review_node)

    # ===== 入口 =====
    workflow.set_entry_point("planner")

    # ===== Planner → Router =====
    workflow.add_edge("planner", "router")

    # ===== Router → 条件分发 =====
    workflow.add_conditional_edges(
        "router",
        should_retrieve,
        {
            "retrieve": "parallel_retrieval",
            "skip": "writer",
        },
    )

    # ===== ParallelRetrieval → Writer =====
    workflow.add_edge("parallel_retrieval", "writer")

    # ===== Writer → 条件：评审或快速完成（快速模式跳过评审） =====
    workflow.add_conditional_edges(
        "writer",
        should_review,
        {
            "review": "parallel_review",
            "skip": END,
        },
    )

    # ===== ParallelReview → 条件 =====
    workflow.add_conditional_edges(
        "parallel_review",
        should_revise,
        {
            "revise": "writer",
            "accept": END,
        },
    )

    # ===== 编译（带内存检查点，支持对话历史）=====
    memory = MemorySaver()
    compiled = workflow.compile(checkpointer=memory)

    return compiled


# ==================== 全局图实例（单例）====================

_graph = None


def get_graph():
    """获取编译后的工作流图（单例）"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ==================== 便捷函数 ====================

async def run_interview_workflow(
    query: str,
    session_id: str = "default",
    user_profile: dict = None,
    fast: bool = False,
) -> AgentState:
    """
    运行完整的面试工作流

    Args:
        query: 面试问题
        session_id: 会话ID（用于对话历史追踪）
        user_profile: 用户画像（如果已预先加载）
        fast: 快速模式（跳过并行评审与修订回环，适合面试对练/实时预览场景）

    Returns:
        包含最终回答和评审结果的 AgentState
    """
    graph = get_graph()
    initial = create_initial_state(query, mode="interview")

    if user_profile:
        initial["user_profile"] = user_profile
        initial["profile_initialized"] = True

    # 快速模式：跳过评审 + 修订回环，直接 writer → END
    if fast:
        initial["planner_decisions"] = {**initial.get("planner_decisions", {}), "skip_review": True}

    config = {"configurable": {"thread_id": session_id}}

    final = None
    async for event in graph.astream(initial, config):
        for node_name, node_state in event.items():
            final = node_state

    return final or initial


async def run_interview_stream(
    query: str,
    session_id: str = "default",
    user_profile: dict = None,
):
    """
    流式运行面试工作流（SSE模式）

    在每个节点完成后 yield 进度事件
    """
    import json
    import time

    graph = get_graph()
    initial = create_initial_state(query, mode="interview")

    if user_profile:
        initial["user_profile"] = user_profile
        initial["profile_initialized"] = True

    config = {"configurable": {"thread_id": session_id}}

    yield {"type": "start", "node": "__start__", "content": "开始处理..."}

    final_state = None
    async for event in graph.astream(initial, config):
        for node_name, node_state in event.items():
            final_state = node_state

            # ===== Planner: 动态调度决策 =====
            if node_name == "planner":
                dec = node_state.get("planner_decisions", {})
                yield {
                    "type": "node_complete", "node": "planner", "status": "success",
                    "data": {
                        "description": dec.get("description", ""),
                        "active_retrievers": dec.get("active_retrievers", []),
                        "active_reviewers": dec.get("active_reviewers", []),
                        "retrieval_top_k": dec.get("retrieval_top_k", 5),
                        "temperature": dec.get("temperature", 0.7),
                        "skip_review": dec.get("skip_review", False),
                    },
                }

            # ===== Router: 问题分类与拆解 =====
            elif node_name == "router":
                yield {
                    "type": "node_complete", "node": "router", "status": "success",
                    "data": {
                        "question_type": node_state.get("question_type", "unknown"),
                        "difficulty": node_state.get("difficulty", "unknown"),
                        "decomposed_queries": node_state.get("decomposed_queries", []),
                    },
                }

            # ===== 并行检索: 3路Agent + Fusion =====
            elif node_name == "parallel_retrieval":
                stats = node_state.get("fusion_stats", {})
                yield {
                    "type": "node_complete", "node": "parallel_retrieval", "status": "success",
                    "data": {
                        "elapsed_ms": stats.get("parallel_elapsed_ms", 0),
                        "total_docs": stats.get("total_docs_retrieved", 0),
                        "active_agents": stats.get("active_agents", []),
                        "agent_timing": stats.get("agent_timing", {}),
                        "agent_breakdown": stats.get("agent_breakdown", {}),
                    },
                }

            # ===== Writer: STAR生成 (含修订回环) =====
            elif node_name == "writer":
                draft = node_state.get("draft_answer", "")
                revision = node_state.get("revision_count", 0)
                citations = node_state.get("citations", [])
                yield {
                    "type": "node_complete", "node": "writer", "status": "success",
                    "data": {
                        "draft": draft,
                        "revision_count": revision,
                        "citations_count": len(citations),
                        "citations": citations[:5],
                    },
                }

            # ===== 并行评审: 3路Reviewer + 多数表决 =====
            elif node_name == "parallel_review":
                votes = node_state.get("revision_votes", {})
                scores = node_state.get("review_scores", {})
                total = node_state.get("review_total", 0)
                needs_rev = node_state.get("needs_revision", False)
                rev_count = node_state.get("revision_count", 0)
                feedback = node_state.get("revision_feedback", "")
                qr = node_state.get("quality_report", {})

                reviewers = {}
                for rn in ["correctness", "completeness", "advantage"]:
                    rd = votes.get(rn, {})
                    reviewers[rn] = {
                        "needs_revision": rd.get("needs_revision", False),
                        "scores": rd.get("scores", {}),
                        "feedback": rd.get("feedback", ""),
                        "confidence": rd.get("confidence", 0),
                    }

                yield {
                    "type": "node_complete", "node": "parallel_review", "status": "success",
                    "data": {
                        "reviewers": reviewers,
                        "review_scores": scores,
                        "review_total": total,
                        "needs_revision": needs_rev,
                        "revision_count": rev_count,
                        "revision_feedback": feedback,
                        "vote_decision": qr.get("votes", {}).get("decision", "accept"),
                        "elapsed_ms": qr.get("parallel_elapsed_ms", 0),
                    },
                }

    # ===== 最终结果 =====
    fa = (final_state or {}).get("final_answer", "") or (final_state or {}).get("draft_answer", "")
    rt = (final_state or {}).get("review_total", 0)
    rc = (final_state or {}).get("revision_count", 0)
    yield {
        "type": "done", "node": "end", "status": "success",
        "data": {
            "final_answer": fa,
            "review_total": rt,
            "revision_count": rc,
        },
    }
