"""LangGraph 工作流组装 + 条件边"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agents.state import AgentState, create_initial_state
from src.agents.planner import profile_analyzer_node
from src.agents.router import question_router_node
from src.agents.retriever_node import experience_retriever_node
from src.agents.writer import star_writer_node
from src.agents.reviewer import quality_reviewer_node
from src.config import settings


def should_revise(state: AgentState) -> Literal["revise", "accept"]:
    """
    条件边：决定是否需要修订

    - total_score >= MIN_REVIEW_SCORE (20) → accept (通过)
    - total_score < 20 AND revision_count < MAX_REVISION_ROUNDS → revise
    - revision_count >= MAX_REVISION_ROUNDS → accept (强制通过)
    """
    total = state.get("review_total", 0)
    revision_count = state.get("revision_count", 0)
    needs_revision = state.get("needs_revision", False)

    if revision_count >= settings.MAX_REVISION_ROUNDS:
        return "accept"

    if total >= settings.MIN_REVIEW_SCORE and not needs_revision:
        return "accept"

    if total < settings.MIN_REVIEW_SCORE or needs_revision:
        return "revise"

    return "accept"


def build_graph() -> StateGraph:
    """
    构建 5 节点 LangGraph 工作流：

    START → ProfileAnalyzer → QuestionRouter → ExperienceRetriever → STARWriter → QualityReviewer
                                                                           ↑              |
                                                                           └── revise ────┘
                                                                                |
                                                                           accept → END
    """
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("profile_analyzer", profile_analyzer_node)
    workflow.add_node("question_router", question_router_node)
    workflow.add_node("experience_retriever", experience_retriever_node)
    workflow.add_node("star_writer", star_writer_node)
    workflow.add_node("quality_reviewer", quality_reviewer_node)

    # 设置入口
    workflow.set_entry_point("profile_analyzer")

    # 线性边
    workflow.add_edge("profile_analyzer", "question_router")
    workflow.add_edge("question_router", "experience_retriever")
    workflow.add_edge("experience_retriever", "star_writer")
    workflow.add_edge("star_writer", "quality_reviewer")

    # 条件边：评审后决定修订还是结束
    workflow.add_conditional_edges(
        "quality_reviewer",
        should_revise,
        {
            "revise": "star_writer",   # 返回 Writer 重新生成
            "accept": END,             # 通过评审，结束
        }
    )

    # 编译（带内存检查点，支持会话持久化）
    memory = MemorySaver()
    compiled = workflow.compile(checkpointer=memory)

    return compiled


# 全局编译好的图实例
_graph = None


def get_graph() -> StateGraph:
    """获取全局编译好的工作流图"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_interview_workflow(
    query: str,
    session_id: str = "default",
    user_profile: dict = None,
) -> AgentState:
    """
    运行面试工作流（便捷函数）

    Args:
        query: 面试问题
        session_id: 会话 ID（用于多轮对话记忆）
        user_profile: 预设的用户画像（跳过 ProfileAnalyzer）

    Returns:
        最终的 AgentState
    """
    graph = get_graph()
    initial_state = create_initial_state(query, mode="interview")

    if user_profile:
        initial_state["user_profile"] = user_profile
        initial_state["profile_initialized"] = True

    config = {"configurable": {"thread_id": session_id}}

    final_state = None
    async for event in graph.astream(initial_state, config):
        for node_name, node_state in event.items():
            final_state = node_state

    return final_state or initial_state


async def run_interview_stream(
    query: str,
    session_id: str = "default",
    user_profile: dict = None,
):
    """
    流式运行面试工作流（用于 SSE 端点）

    在 STARWriter 节点中流式生成回答
    """
    import asyncio
    from src.agents.writer import star_writer_stream

    graph = get_graph()
    initial_state = create_initial_state(query, mode="interview")

    if user_profile:
        initial_state["user_profile"] = user_profile
        initial_state["profile_initialized"] = True

    config = {"configurable": {"thread_id": session_id}}

    # 先运行前 3 个节点（到检索完成）
    async for event in graph.astream(initial_state, config):
        for node_name, node_state in event.items():
            if node_name == "experience_retriever":
                # 检索完成，开始流式生成
                state_for_writer = node_state
                async for chunk in star_writer_stream(state_for_writer):
                    yield {"type": "chunk", "content": chunk}

                # 运行评审
                review_state = await quality_reviewer_node(state_for_writer)
                yield {
                    "type": "review",
                    "scores": review_state.get("review_scores", {}),
                    "total": review_state.get("review_total", 0),
                    "needs_revision": review_state.get("needs_revision", False),
                }

                # 如果需要修订，重新生成
                while review_state.get("needs_revision") and review_state.get("revision_count", 0) < settings.MAX_REVISION_ROUNDS:
                    yield {"type": "revision_start", "count": review_state.get("revision_count", 0)}
                    revised_state = await star_writer_node(review_state)
                    async for chunk in star_writer_stream(revised_state):
                        yield {"type": "chunk", "content": chunk}
                    review_state = await quality_reviewer_node(revised_state)
                    yield {
                        "type": "review",
                        "scores": review_state.get("review_scores", {}),
                        "total": review_state.get("review_total", 0),
                        "needs_revision": review_state.get("needs_revision", False),
                    }

                yield {"type": "done", "final_answer": review_state.get("final_answer", "")}
                return

    yield {"type": "error", "content": "工作流执行异常"}
