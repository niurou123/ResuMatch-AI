"""Node 2: QuestionRouter - 规则化问题分类（0s 延迟）"""
import re
from typing import Dict, Any, List, Tuple
from src.agents.state import AgentState


# ===== 分类规则（关键词 + 正则） =====
CATEGORY_RULES: Dict[str, List[str]] = {
    "technical_depth": [
        # 技术原理类
        r'(?:原理|底层|源码|实现|机制|怎么工作|如何实现)',
        r'(?:时间复杂度|空间复杂度|性能优化|内存管理|并发|多线程)',
        r'(?:设计模式|架构|微服务|分布式|CAP|一致性)',
        r'(?:算法|数据结构|排序|搜索|动态规划|回溯|贪心)',
        r'(?:HTTP|TCP|UDP|REST|gRPC|WebSocket)',
    ],
    "project_followup": [
        # 项目追问类
        r'(?:项目|Project|系统|平台|助手|工具).{0,10}(?:中|里|怎么|如何|为什么|介绍)',
        r'(?:你在|你负责|你做了|你的角色|你的贡献)',
        r'(?:遇到.*挑战|遇到.*困难|怎么解决|如何优化)',
        r'(?:技术选型|为什么选择|为什么用)',
        r'(?:最.*项目|代表.*项目|印象.*深)',
    ],
    "behavioral": [
        # 行为面试类
        r'(?:团队合作|团队协作|冲突|矛盾|分歧)',
        r'(?:领导|管理|带领|指导|mentor)',
        r'(?:失败|错误|教训|重来|后悔)',
        r'(?:压力|加班|deadline|紧迫)',
        r'(?:优缺点|优势|劣势|不足|改进)',
        r'(?:职业规划|职业发展|五年|目标)',
    ],
    "self_intro": [
        # 自我介绍类
        r'(?:自我介绍|介绍一下自己|说说你|聊聊你)',
        r'(?:为什么.*适合|为什么.*录用|为什么.*选择你)',
    ],
}

# 难度关键词
DIFFICULTY_KEYWORDS = {
    "advanced": [r'(?:深度|底层|源码|原理|架构|设计|分布式|高并发|优化)'],
    "basic": [r'(?:基础|简单|入门|什么是|介绍一下|说说)'],
}


async def question_router_node(state: AgentState) -> AgentState:
    """
    Node 2: QuestionRouter

    规则化分类，0s LLM 延迟。
    使用关键词 + 正则匹配进行分类。
    """
    query = state.get("query", "")

    if not query.strip():
        state["question_type"] = "general"
        state["difficulty"] = "basic"
        return state

    # 分类
    question_type = _classify(query)
    difficulty = _estimate_difficulty(query)

    # 复杂问题拆解
    decomposed = _decompose_query(query, question_type)

    state["question_type"] = question_type
    state["difficulty"] = difficulty
    state["decomposed_queries"] = decomposed

    return state


def _classify(query: str) -> str:
    """规则化问题分类"""
    scores: Dict[str, int] = {}

    for category, patterns in CATEGORY_RULES.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            score += len(matches)
        scores[category] = score

    # 找最高分
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    return "general"


def _estimate_difficulty(query: str) -> str:
    """估算问题难度"""
    advanced_score = sum(
        len(re.findall(p, query, re.IGNORECASE))
        for p in DIFFICULTY_KEYWORDS["advanced"]
    )
    basic_score = sum(
        len(re.findall(p, query, re.IGNORECASE))
        for p in DIFFICULTY_KEYWORDS["basic"]
    )

    if advanced_score > basic_score:
        return "advanced"
    elif basic_score > advanced_score:
        return "basic"
    return "intermediate"


def _decompose_query(query: str, question_type: str) -> List[str]:
    """将复杂问题拆解为子查询（用于多角度检索）"""
    decomposed = [query]  # 始终包含原始查询

    if question_type == "project_followup":
        # 拆解项目追问
        if "挑战" in query or "困难" in query:
            decomposed.append("技术难点 问题解决 性能瓶颈")
        if "贡献" in query or "角色" in query:
            decomposed.append("核心贡献 关键成果 量化指标")
        if "技术" in query or "架构" in query:
            decomposed.append("技术栈 架构设计 技术选型")

    elif question_type == "technical_depth":
        # 拆解技术深问
        if any(kw in query for kw in ["区别", "对比", "vs"]):
            decomposed.append("技术对比 优缺点 适用场景")
        if any(kw in query for kw in ["原理", "机制", "流程"]):
            decomposed.append("工作原理 核心机制 数据流")

    elif question_type == "behavioral":
        # 拆解行为面试
        if "团队" in query:
            decomposed.append("协作经验 沟通能力 团队角色")
        if "失败" in query or "错误" in query:
            decomposed.append("经验教训 改进措施 复盘总结")

    return decomposed[:3]  # 最多3个子查询
