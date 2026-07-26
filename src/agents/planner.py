"""
Node 0: DynamicPlanner - 多Agent调度指挥官

真正的动态Planner：根据问题类型、难度和用户画像，
智能决定激活哪些Agent、检索深度、评审重点。
"""
from typing import Dict, Any, List
from src.agents.state import AgentState


# ===== 按问题类型的调度策略表 =====
SCHEDULING_POLICY: Dict[str, Dict[str, Any]] = {
    "technical_depth": {
        "active_retrievers": ["keyword", "semantic", "graph"],
        "active_reviewers": ["correctness", "completeness", "advantage"],
        "decomposition_depth": 2,
        "retrieval_top_k": 10,
        "revise_priority": "correctness",
        "temperature": 0.3,
        "description": "技术深度问题：全部3路检索+严格正确性审查",
    },
    "project_followup": {
        "active_retrievers": ["keyword", "semantic", "graph"],
        "active_reviewers": ["correctness", "completeness", "advantage"],
        "decomposition_depth": 2,
        "retrieval_top_k": 8,
        "revise_priority": "completeness",
        "temperature": 0.5,
        "description": "项目追问：全检索+重点检查STAR完整性",
    },
    "behavioral": {
        "active_retrievers": ["semantic", "graph"],
        "active_reviewers": ["completeness", "advantage"],
        "decomposition_depth": 1,
        "retrieval_top_k": 6,
        "revise_priority": "advantage",
        "temperature": 0.6,
        "description": "行为面试：语义+图谱检索，重优势展示",
    },
    "self_intro": {
        "active_retrievers": ["semantic"],
        "active_reviewers": ["completeness"],
        "decomposition_depth": 0,
        "retrieval_top_k": 5,
        "revise_priority": "completeness",
        "temperature": 0.7,
        "description": "自我介绍：仅语义检索，轻量审查",
    },
    "general": {
        "active_retrievers": ["semantic"],
        "active_reviewers": ["completeness"],
        "decomposition_depth": 0,
        "retrieval_top_k": 5,
        "revise_priority": "completeness",
        "temperature": 0.7,
        "description": "通用问题：单路检索，轻量审查",
    },
}

# 难度系数调整
DIFFICULTY_MODIFIERS = {
    "advanced": {
        "decomposition_depth": +1,
        "retrieval_top_k": +3,
    },
    "intermediate": {},
    "basic": {
        "decomposition_depth": -1,
        "retrieval_top_k": -2,
    },
}


async def dynamic_planner_node(state: AgentState) -> AgentState:
    """
    Node 0: DynamicPlanner

    职责：
    1. 基于问题类型加载调度策略
    2. 根据难度调整参数
    3. 特殊模式处理（自我介绍、JD匹配）
    4. 输出 planner_decisions 供下游Agent使用
    """
    mode = state.get("mode", "interview")
    question_type = state.get("question_type", "general")
    difficulty = state.get("difficulty", "intermediate")
    user_profile = state.get("user_profile", {})

    # ===== 模式特殊处理 =====
    if mode == "self_intro":
        state["planner_decisions"] = {
            "active_retrievers": ["semantic"],
            "active_reviewers": [],
            "decomposition_depth": 0,
            "retrieval_top_k": 5,
            "revise_priority": "completeness",
            "temperature": 0.7,
            "skip_review": True,
            "description": "自我介绍模式：轻量检索，跳过审查",
        }
        return state

    if mode == "jd_match":
        state["planner_decisions"] = {
            "active_retrievers": ["keyword", "graph"],
            "active_reviewers": [],
            "decomposition_depth": 0,
            "retrieval_top_k": 15,
            "revise_priority": "completeness",
            "temperature": 0.3,
            "skip_review": True,
            "description": "JD匹配模式：关键词+图谱检索，无审查",
        }
        return state

    # ===== 加载基础策略 =====
    policy = SCHEDULING_POLICY.get(question_type, SCHEDULING_POLICY["general"]).copy()

    # ===== 难度调整 =====
    modifier = DIFFICULTY_MODIFIERS.get(difficulty, {})
    if "decomposition_depth" in modifier:
        policy["decomposition_depth"] = max(0, min(3,
            policy["decomposition_depth"] + modifier["decomposition_depth"]))
    if "retrieval_top_k" in modifier:
        policy["retrieval_top_k"] = max(3, min(20,
            policy["retrieval_top_k"] + modifier["retrieval_top_k"]))

    # ===== 基于用户画像微调 =====
    has_many_projects = len(user_profile.get("projects", [])) > 3
    has_many_skills = len(user_profile.get("skills", [])) > 10

    if has_many_projects and question_type == "project_followup":
        # 项目多的候选人，增大召回量
        policy["retrieval_top_k"] += 2

    if not has_many_skills and question_type == "technical_depth":
        # 技能少的候选人，去掉关键词检索（避免空结果）
        if "keyword" in policy["active_retrievers"] and len(policy["active_retrievers"]) > 1:
            policy["active_retrievers"].remove("keyword")

    # ===== 输出决策 =====
    state["planner_decisions"] = policy

    # 将 top_k 传递给后续检索Agent使用
    state["_retrieval_top_k"] = policy["retrieval_top_k"]
    state["_decomposition_depth"] = policy["decomposition_depth"]
    state["_temperature"] = policy["temperature"]

    return state


def get_planner_summary(state: AgentState) -> str:
    """获取Planner决策的可读摘要（用于调试和日志）"""
    decisions = state.get("planner_decisions", {})
    if not decisions:
        return "Planner未执行"

    lines = [
        f"📋 Planner决策: {decisions.get('description', 'N/A')}",
        f"  🔍 检索Agent: {decisions.get('active_retrievers', [])}",
        f"  ✅ 评审Agent: {decisions.get('active_reviewers', [])}",
        f"  📊 检索Top-K: {decisions.get('retrieval_top_k', 'N/A')}",
        f"  🔄 拆解深度: {decisions.get('decomposition_depth', 'N/A')}",
        f"  🎯 修订优先级: {decisions.get('revise_priority', 'N/A')}",
    ]
    return "\n".join(lines)
