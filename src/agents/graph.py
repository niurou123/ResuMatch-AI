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
    Planner + Router联合决策：是否需要检索增强？

    - 自我介绍模式：跳过检索（Profile数据已足够）
    - 通用问题：跳过检索
    - 技术/项目/行为问题：执行检索
    """
    mode = state.get("mode", "interview")
    qtype = state.get("question_type", "general")

    # 模式级别跳过
    if mode in ("self_intro", "jd_match"):
        return "skip"

    # 问题类型级别跳过
    if qtype in ("general", "self_intro"):
        return "skip"

    # 有简历数据才检索
    if state.get("profile_initialized") or state.get("reranked_context"):
        return "retrieve"

    # 默认跳过（没有索引数据时无意义检索）
    return "skip"


def should_revise(state: AgentState) -> Literal["revise", "accept"]:
    """
    多数表决决策：是否需要修订？

    基于 vote_node 的结果：
    - needs_revision=True 且 revision_count < MAX_REVISION_ROUNDS → 修订
    - 否则 → 接受
    """
    needs_revision = state.get("needs_revision", False)
    revision_count = state.get("revision_count", 0)

    if needs_revision and revision_count < settings.MAX_REVISION_ROUNDS:
        return "revise"
    return "accept"


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

    # ===== Writer → ParallelReview =====
    workflow.add_edge("writer", "parallel_review")

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
) -> AgentState:
    """
    运行完整的面试工作流

    Args:
        query: 面试问题
        session_id: 会话ID（用于对话历史追踪）
        user_profile: 用户画像（如果已预先加载）

    Returns:
        包含最终回答和评审结果的 AgentState
    """
    graph = get_graph()
    initial = create_initial_state(query, mode="interview")

    if user_profile:
        initial["user_profile"] = user_profile
        initial["profile_initialized"] = True

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

    graph = get_graph()
    initial = create_initial_state(query, mode="interview")

    if user_profile:
        initial["user_profile"] = user_profile
        initial["profile_initialized"] = True

    config = {"configurable": {"thread_id": session_id}}

    yield {"type": "start", "content": "开始处理..."}

    async for event in graph.astream(initial, config):
        for node_name, node_state in event.items():
            # 进度事件
            if node_name == "planner":
                summary = get_planner_summary(node_state)
                yield {"type": "progress", "content": f"Planner决策完成\n{summary}"}

            elif node_name == "router":
                qtype = node_state.get("question_type", "unknown")
                difficulty = node_state.get("difficulty", "unknown")
                yield {"type": "progress", "content": f"问题分类: {qtype} ({difficulty})"}

            elif node_name == "parallel_retrieval":
                stats = node_state.get("fusion_stats", {})
                yield {
                    "type": "progress",
                    "content": f"并行检索完成 ({stats.get('parallel_elapsed_ms', 0)}ms) | "
                              f"召回: {stats.get('total_docs_retrieved', 0)}篇",
                }

            elif node_name == "writer":
                draft = node_state.get("draft_answer", "")
                revision = node_state.get("revision_count", 0)
                tag = f"(第{revision}轮修订)" if revision > 0 else ""
                yield {"type": "chunk", "content": draft, "revision": revision}

            elif node_name == "parallel_review":
                report = node_state.get("quality_report", {})
                votes = report.get("votes", {})
                total = node_state.get("review_total", 0)
                needs_rev = node_state.get("needs_revision", False)

                yield {
                    "type": "review",
                    "content": f"评审完成 | 总分: {total}/25 | "
                              f"投票: {votes.get('yes', 0)}修订/{votes.get('no', 0)}接受 | "
                              f"决策: {'修订' if needs_rev else '通过'}",
                    "scores": node_state.get("review_scores", {}),
                    "total": total,
                    "needs_revision": needs_rev,
                }

    # 最终答案
    yield {
        "type": "done",
        "content": final.get("final_answer", final.get("draft_answer", "")),
        "final_answer": final.get("final_answer", final.get("draft_answer", "")),
        "review_total": final.get("review_total", 0),
        "quality_report": final.get("quality_report", {}),
    }
