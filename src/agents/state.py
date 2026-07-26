"""LangGraph Agent 状态定义 - 多Agent架构"""
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """ResuMatch AI 工作流全局状态 - 支持多Agent并行"""

    # ===== 输入 =====
    query: str                          # 用户问题
    mode: str                           # interview / self_intro / jd_match

    # ===== 简历上下文（长期记忆）=====
    user_profile: Dict[str, Any]        # 结构化简历信息
    profile_initialized: bool           # 简历是否已加载

    # ===== Planner 动态调度 =====
    planner_decisions: Dict[str, Any]   # Planner的调度决策
    # { "active_retrievers": ["keyword","semantic","graph"],
    #   "active_reviewers": ["correctness","completeness","advantage"],
    #   "decomposition_depth": 1, "retrieval_top_k": 8,
    #   "revise_priority": "advantage", "temperature": 0.7 }

    # ===== 路由结果 =====
    question_type: str                  # technical_depth / project_followup / behavioral / self_intro / general
    difficulty: str                     # basic / intermediate / advanced
    decomposed_queries: List[str]       # 复杂问题拆解的子问题列表

    # ===== 检索增强 =====
    hypothetical_answer: str            # HyDE：LLM 生成的假设回答
    self_query_filter: Dict[str, Any]   # Self-Query：结构化 metadata 过滤条件
    knowledge_expansions: List[str]     # Skill Graph：知识图谱查询扩展结果

    # ===== 3路并行检索结果 =====
    keyword_results: List[Dict[str, Any]]    # Agent 1: 关键词精确匹配
    semantic_results: List[Dict[str, Any]]   # Agent 2: 语义向量检索
    graph_results: List[Dict[str, Any]]      # Agent 3: 知识图谱推理
    fusion_stats: Dict[str, Any]             # Fusion 统计信息

    # ===== 融合后的检索结果 =====
    retrieved_skills: List[Dict[str, Any]]       # 匹配的技能
    retrieved_projects: List[Dict[str, Any]]     # 匹配的项目经验
    retrieved_achievements: List[Dict[str, Any]] # 匹配的成果数据
    retrieved_education: List[Dict[str, Any]]    # 匹配的教育背景
    reranked_context: List[Dict[str, Any]]       # Cross-Encoder 精排后的最终上下文

    # ===== 生成结果 =====
    draft_answer: str                   # STARWriter 生成的草稿
    candidate_answers: List[Dict[str, Any]]  # 候选回答（多版本）
    stream_chunks: List[str]            # 流式生成的 chunk 缓存
    writer_queries: List[Dict[str, Any]]     # Writer向Reviewer发起的咨询

    # ===== 3路并行评审结果 =====
    review_correctness: Dict[str, Any]   # Reviewer 1: 正确性评审
    review_completeness: Dict[str, Any]  # Reviewer 2: 完整性评审
    review_advantage: Dict[str, Any]     # Reviewer 3: 优势展示评审
    revision_votes: Dict[str, Dict[str, Any]]  # 投票详情
    # { "correctness": {"needs_revision": true, "feedback": "...", "score": 3},
    #   "completeness": {"needs_revision": false, "feedback": "...", "score": 4},
    #   "advantage": {"needs_revision": true, "feedback": "...", "score": 2} }

    # ===== 综合评审结果 =====
    review_scores: Dict[str, float]     # 聚合后的5维评分
    review_total: float                 # 总分（0-25）
    revision_count: int                 # 已修订次数
    needs_revision: bool                # 是否需要修订（多数投票结果）
    revision_feedback: str              # 聚合的修订意见

    # ===== 会话记忆 =====
    messages: Annotated[list, add_messages]  # LangGraph 消息历史
    conversation_history: List[Dict[str, str]]  # 短期对话历史
    session_topics: List[str]           # 中期主题追踪
    memory_summary: str                 # 压缩后的长期摘要

    # ===== 最终输出 =====
    final_answer: str                   # 最终回答
    citations: List[Dict[str, Any]]     # 引用来源
    quality_report: Dict[str, Any]      # LLM-Judge 评测报告
    error: Optional[str]                # 错误信息


def create_initial_state(query: str, mode: str = "interview") -> AgentState:
    """创建初始状态 - 多Agent架构"""
    return AgentState(
        query=query,
        mode=mode,
        profile_initialized=False,
        planner_decisions={},
        question_type="general",
        difficulty="basic",
        decomposed_queries=[],
        knowledge_expansions=[],
        keyword_results=[],
        semantic_results=[],
        graph_results=[],
        fusion_stats={},
        retrieved_skills=[],
        retrieved_projects=[],
        retrieved_achievements=[],
        retrieved_education=[],
        reranked_context=[],
        candidate_answers=[],
        stream_chunks=[],
        writer_queries=[],
        review_correctness={},
        review_completeness={},
        review_advantage={},
        revision_votes={},
        review_scores={},
        review_total=0.0,
        revision_count=0,
        needs_revision=False,
        revision_feedback="",
        conversation_history=[],
        session_topics=[],
        memory_summary="",
        final_answer="",
        citations=[],
        quality_report={},
        error=None,
    )
