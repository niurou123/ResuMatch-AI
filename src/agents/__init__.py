"""
ResuMatch AI - 多Agent协作层 (v3.0)

架构：
  dynamic_planner → question_router → parallel_retrieval (3路并行)
    → star_writer (Agent通信) → parallel_review (3路并行+投票) → END/revise

模块：
  state.py:         AgentState 全局状态定义
  planner.py:       DynamicPlanner - 按问题类型智能调度
  router.py:        QuestionRouter - 规则化问题分类（0s延迟）
  retriever_node.py: 3路并行检索Agent + Fusion投票
  writer.py:        STARWriter + Agent间通信集成
  reviewer.py:      3路并行评审Agent + 多数表决
  communication.py: Agent间双向通信协议
  graph.py:         LangGraph工作流编排
"""

from src.agents.state import AgentState, create_initial_state
from src.agents.planner import dynamic_planner_node, get_planner_summary
from src.agents.router import question_router_node
from src.agents.retriever_node import (
    keyword_agent,
    semantic_agent,
    knowledge_graph_agent,
    parallel_retrieval_node,
    fusion_node,
)
from src.agents.writer import star_writer_node, star_writer_stream
from src.agents.reviewer import (
    reviewer_correctness,
    reviewer_completeness,
    reviewer_advantage,
    parallel_review_node,
    vote_node,
)
from src.agents.communication import (
    AgentMessage,
    writer_consult_reviewer,
    writer_check_factual_claim,
    writer_check_completeness,
    writer_check_advantage_impact,
    get_communication_summary,
)
from src.agents.graph import (
    build_graph,
    get_graph,
    run_interview_workflow,
    run_interview_stream,
)

__all__ = [
    # State
    "AgentState",
    "create_initial_state",
    # Planner
    "dynamic_planner_node",
    "get_planner_summary",
    # Router
    "question_router_node",
    # Retrievers
    "keyword_agent",
    "semantic_agent",
    "knowledge_graph_agent",
    "parallel_retrieval_node",
    "fusion_node",
    # Writer
    "star_writer_node",
    "star_writer_stream",
    # Reviewers
    "reviewer_correctness",
    "reviewer_completeness",
    "reviewer_advantage",
    "parallel_review_node",
    "vote_node",
    # Communication
    "AgentMessage",
    "writer_consult_reviewer",
    "writer_check_factual_claim",
    "writer_check_completeness",
    "writer_check_advantage_impact",
    "get_communication_summary",
    # Graph
    "build_graph",
    "get_graph",
    "run_interview_workflow",
    "run_interview_stream",
]
