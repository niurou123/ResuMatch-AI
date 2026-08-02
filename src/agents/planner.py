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
        "skip_review": False,
        "description": "技术深度：3路检索+3路评审",
    },
    "project_followup": {
        "active_retrievers": ["keyword", "semantic", "graph"],
        "active_reviewers": ["correctness", "completeness", "advantage"],
        "decomposition_depth": 2,
        "retrieval_top_k": 8,
        "revise_priority": "completeness",
        "temperature": 0.5,
        "skip_review": False,
        "description": "项目追问：3路检索+3路评审",
    },
    "behavioral": {
        "active_retrievers": ["keyword", "semantic", "graph"],
        "active_reviewers": ["correctness", "completeness", "advantage"],
        "decomposition_depth": 1,
        "retrieval_top_k": 6,
        "revise_priority": "advantage",
        "temperature": 0.6,
        "skip_review": False,
        "description": "行为面试：3路检索+3路评审",
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
        "active_retrievers": ["keyword", "semantic", "graph"],
        "active_reviewers": ["correctness", "completeness", "advantage"],
        "decomposition_depth": 0,
        "retrieval_top_k": 5,
        "revise_priority": "completeness",
        "temperature": 0.7,
        "description": "通用：3路检索+3路评审",
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
    # 从 user_profile 获取技能数（兼容两种数据结构）
    skills_count = len(user_profile.get("skills", []))
    projects_count = len(user_profile.get("projects", []))
    # 如果 user_profile 使用的是 indexed_docs 结构，从中推断
    if not skills_count or not projects_count:
        indexed = user_profile.get("indexed_docs", [])
        if indexed:
            skills_count = sum(1 for d in indexed if d.get("collection") == "skills")
            projects_count = sum(1 for d in indexed if d.get("collection") == "projects")
    # 兜底：从 collections 统计推断
    collections = user_profile.get("collections", {})
    if not skills_count and collections:
        skills_count = collections.get("skills", 0)
    if not projects_count and collections:
        projects_count = collections.get("projects", 0)

    has_many_projects = projects_count > 3
    has_many_skills = skills_count > 10

    retriever_list = policy.get("active_retrievers", [])
    print(f"[Planner] question_type={question_type} has_many_skills={has_many_skills} skills_count={skills_count} projects_count={projects_count}")
    print(f"[Planner] active before adjust: {retriever_list}")

    # 如果有数据但 planner 因为 has_many_skills=False 移除了 keyword，重新补上
    if "keyword" not in retriever_list and skills_count > 0:
        retriever_list = list(retriever_list) + ["keyword"]
    if "graph" not in retriever_list and skills_count > 5:
        retriever_list = list(retriever_list) + ["graph"]

    # 去重后回写
    policy["active_retrievers"] = list(dict.fromkeys(retriever_list))

    if has_many_projects and question_type == "project_followup":
        policy["retrieval_top_k"] += 2

    print(f"[Planner] active after adjust: {policy['active_retrievers']}")

    # ===== 输出决策 =====
    # 保留快速模式标志：若入口已设置 skip_review（如面试对练 fast=True），强制覆盖回 policy
    if state.get("planner_decisions", {}).get("skip_review"):
        policy["skip_review"] = True
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
