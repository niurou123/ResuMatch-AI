"""
多Agent并行评审 - 3路独立Reviewer + 多数表决

架构：
  Reviewer 1 (正确性): 检查事实准确性、STAR结构、引用真实性
  Reviewer 2 (完整性): 检查问题覆盖度、关键点遗漏
  Reviewer 3 (优势): 检查个人能力展示、竞争力体现

  Vote节点: 多数表决 → revise/accept
  至少2/3投票"需要修订"才触发修订回环
"""
import asyncio
import time
import json
import re
from typing import Dict, Any, List
from src.agents.state import AgentState
from src.core.llm_client import get_client, Message


# ============ Reviewer 1: 正确性评审 ============
REVIEWER_CORRECTNESS_PROMPT = """你是一个严格的**正确性评审官**。你的唯一职责是检查面试回答的事实正确性和结构完整性。

## 评审维度
1. **事实准确性**: 回答中的技术描述、项目细节是否与简历素材一致？
2. **STAR结构**: 是否完整包含 Situation → Task → Action → Result 四要素？
3. **引用真实性**: 回答中的数字、成果是否来自素材而非编造？
4. **技术表述**: 技术术语使用是否准确？有没有概念混淆？

## 评分标准（每项1-5分）
- 5: 完全准确，结构严谨
- 3: 基本正确，有小瑕疵
- 1: 存在事实错误或结构严重缺失

严格返回 JSON（不要其他文字）：
{
    "needs_revision": true/false,
    "scores": {"factual_accuracy": 4, "star_structure": 5, "citation_truthfulness": 4, "technical_precision": 3},
    "critical_issues": ["具体的事实错误或结构缺陷"],
    "feedback": "如果needs_revision=true，提供具体修改建议；否则为空字符串",
    "confidence": 0.85
}"""

REVIEWER_COMPLETENESS_PROMPT = """你是一个细致的**完整性评审官**。你的唯一职责是检查回答是否全面覆盖了问题的所有方面。

## 评审维度
1. **问题覆盖度**: 回答是否直接回应了问题的核心？有没有偏题？
2. **关键点覆盖**: 问题涉及的每个子要点是否都被触及？
3. **深度与广度**: 回答的深度是否匹配问题的难度？
4. **遗漏检测**: 问题中隐含的需求是否被忽略了？

## 评分标准（每项1-5分）
- 5: 全面覆盖问题的所有方面
- 3: 覆盖主要内容，略有遗漏
- 1: 严重偏题或大量遗漏

严格返回 JSON（不要其他文字）：
{
    "needs_revision": true/false,
    "scores": {"question_coverage": 4, "key_points": 3, "depth_match": 4, "gap_detection": 3},
    "missing_aspects": ["回答未覆盖的关键点"],
    "feedback": "如果needs_revision=true，指出遗漏了什么；否则为空字符串",
    "confidence": 0.85
}"""

REVIEWER_ADVANTAGE_PROMPT = """你是一个敏锐的**竞争力评审官**。你的唯一职责是检查回答是否充分展示了候选人的独特优势。

## 评审维度
1. **个人独特性**: 回答是否展示了候选人独特的贡献？还是泛泛而谈？
2. **量化成果展示**: 是否充分使用了数字、百分比来证明能力？
3. **第一人称叙述**: 是否清晰表达了"我"做了什么，而非"我们"？
4. **竞争力体现**: 回答是否让候选人在竞争中脱颖而出？

## 评分标准（每项1-5分）
- 5: 极具说服力，充分展示个人价值
- 3: 基本展示了能力，但不够突出
- 1: 毫无个人特色，与其他候选人无差异

严格返回 JSON（不要其他文字）：
{
    "needs_revision": true/false,
    "scores": {"personal_uniqueness": 4, "quantitative_showcase": 3, "first_person_clarity": 4, "competitiveness": 3},
    "improvement_areas": ["可以更突出个人特色的方面"],
    "feedback": "如果needs_revision=true，提供如何更好展示优势的建议；否则为空字符串",
    "confidence": 0.85
}"""


# ============ 构建评审 prompt ============

def _build_review_user_prompt(state: AgentState, reviewer_type: str) -> str:
    """构建不同Reviewer的user prompt"""
    query = state.get("query", "")
    answer = state.get("draft_answer", state.get("final_answer", ""))
    context = state.get("reranked_context", [])

    context_text = ""
    if context:
        for i, ctx in enumerate(context[:8]):
            coll = ctx.get("collection", "")
            content = ctx.get("content", "")[:300]
            meta = ctx.get("metadata", {})
            name = meta.get("name", "")
            context_text += f"{i+1}. [{coll}] {name}: {content}\n"

    base = f"""## 面试问题
{query}

## 候选人回答
{answer}

## 简历素材（用于验证）
{context_text if context_text else "无可用素材"}

请根据你的专业领域进行评审，返回 JSON。"""

    return base


# ============ 3个独立评审Agent ============

async def reviewer_correctness(state: AgentState) -> AgentState:
    """
    Reviewer 1: 正确性专家
    关注：事实准确性、STAR结构完整性、引用真实性、技术表述准确性
    """
    answer = state.get("draft_answer", state.get("final_answer", ""))
    if not answer or len(answer) < 20:
        state["review_correctness"] = {
            "needs_revision": True,
            "scores": {"factual_accuracy": 1, "star_structure": 1, "citation_truthfulness": 1, "technical_precision": 1},
            "critical_issues": ["回答过短，无法评审"],
            "feedback": "请提供更详细的回答（至少包含完整的STAR结构）",
            "confidence": 1.0,
        }
        return state

    try:
        client = get_client()
        messages = [
            Message(role="system", content=REVIEWER_CORRECTNESS_PROMPT),
            Message(role="user", content=_build_review_user_prompt(state, "correctness")),
        ]
        raw = await client.chat_sync(messages, temperature=0.2)
        result = _parse_review_json(raw)

        state["review_correctness"] = result
    except Exception as e:
        state["review_correctness"] = _fallback_correctness_review(state)

    return state


async def reviewer_completeness(state: AgentState) -> AgentState:
    """
    Reviewer 2: 完整性专家
    关注：问题覆盖度、关键点覆盖、深度匹配、遗漏检测
    """
    answer = state.get("draft_answer", state.get("final_answer", ""))
    if not answer or len(answer) < 20:
        state["review_completeness"] = {
            "needs_revision": True,
            "scores": {"question_coverage": 1, "key_points": 1, "depth_match": 1, "gap_detection": 1},
            "missing_aspects": ["回答过短，无法评估完整性"],
            "feedback": "请提供更详细的回答",
            "confidence": 1.0,
        }
        return state

    try:
        client = get_client()
        messages = [
            Message(role="system", content=REVIEWER_COMPLETENESS_PROMPT),
            Message(role="user", content=_build_review_user_prompt(state, "completeness")),
        ]
        raw = await client.chat_sync(messages, temperature=0.2)
        result = _parse_review_json(raw)

        state["review_completeness"] = result
    except Exception as e:
        state["review_completeness"] = _fallback_completeness_review(state)

    return state


async def reviewer_advantage(state: AgentState) -> AgentState:
    """
    Reviewer 3: 优势展示专家
    关注：个人独特性、量化成果、第一人称叙述、竞争力
    """
    answer = state.get("draft_answer", state.get("final_answer", ""))
    if not answer or len(answer) < 20:
        state["review_advantage"] = {
            "needs_revision": True,
            "scores": {"personal_uniqueness": 1, "quantitative_showcase": 1, "first_person_clarity": 1, "competitiveness": 1},
            "improvement_areas": ["回答过短，无法评估优势展示"],
            "feedback": "请提供更详细的回答，突出个人贡献",
            "confidence": 1.0,
        }
        return state

    try:
        client = get_client()
        messages = [
            Message(role="system", content=REVIEWER_ADVANTAGE_PROMPT),
            Message(role="user", content=_build_review_user_prompt(state, "advantage")),
        ]
        raw = await client.chat_sync(messages, temperature=0.2)
        result = _parse_review_json(raw)

        state["review_advantage"] = result
    except Exception as e:
        state["review_advantage"] = _fallback_advantage_review(state)

    return state


# ============ 多数表决 ============

async def vote_node(state: AgentState) -> AgentState:
    """
    多数表决节点：汇总3个Reviewer的结果，做出最终修订决策

    规则：
    - >= 2个Reviewer投票"需要修订" → 触发修订
    - < 2个 → 接受回答
    - 平局 → 正确性Reviewer的票为决定性票
    """
    correctness = state.get("review_correctness", {})
    completeness = state.get("review_completeness", {})
    advantage = state.get("review_advantage", {})

    # 收集投票
    votes = {
        "correctness": {
            "needs_revision": correctness.get("needs_revision", False),
            "scores": correctness.get("scores", {}),
            "feedback": correctness.get("feedback", ""),
            "confidence": correctness.get("confidence", 0.5),
        },
        "completeness": {
            "needs_revision": completeness.get("needs_revision", False),
            "scores": completeness.get("scores", {}),
            "feedback": completeness.get("feedback", ""),
            "confidence": completeness.get("confidence", 0.5),
        },
        "advantage": {
            "needs_revision": advantage.get("needs_revision", False),
            "scores": advantage.get("scores", {}),
            "feedback": advantage.get("feedback", ""),
            "confidence": advantage.get("confidence", 0.5),
        },
    }

    state["revision_votes"] = votes

    # 统计票数
    yes_votes = sum(1 for v in votes.values() if v["needs_revision"])
    no_votes = 3 - yes_votes

    # 多数表决
    if yes_votes >= 2:
        state["needs_revision"] = True
        # 递增修订计数
        revision_count = state.get("revision_count", 0)
        state["revision_count"] = revision_count + 1
        # 聚合反馈（优先高置信度Reviewer的意见）
        sorted_votes = sorted(
            [(k, v) for k, v in votes.items() if v["needs_revision"]],
            key=lambda x: x[1]["confidence"], reverse=True,
        )
        feedback_parts = []
        for reviewer_name, vote in sorted_votes:
            fb = vote.get("feedback", "")
            if fb and fb not in feedback_parts:
                feedback_parts.append(f"【{_reviewer_label(reviewer_name)}】{fb}")
        state["revision_feedback"] = "\n\n".join(feedback_parts)
    else:
        state["needs_revision"] = False
        state["revision_feedback"] = ""

    # 聚合评分
    all_scores = {}
    for reviewer_name, vote in votes.items():
        for dim, score in vote.get("scores", {}).items():
            all_scores[f"{reviewer_name}_{dim}"] = score

    # 计算加权总分（正确性×1.2 + 完整性×1.0 + 优势×0.8）
    c_scores = list(votes["correctness"]["scores"].values())
    m_scores = list(votes["completeness"]["scores"].values())
    a_scores = list(votes["advantage"]["scores"].values())

    c_avg = sum(c_scores) / len(c_scores) if c_scores else 0
    m_avg = sum(m_scores) / len(m_scores) if m_scores else 0
    a_avg = sum(a_scores) / len(a_scores) if a_scores else 0

    weighted_total = (c_avg * 1.2 + m_avg * 1.0 + a_avg * 0.8) / 3.0 * 5  # 归一化到0-25

    state["review_scores"] = all_scores
    state["review_total"] = round(weighted_total, 1)

    # 构建质量报告
    state["quality_report"] = {
        "votes": {
            "yes": yes_votes,
            "no": no_votes,
            "decision": "revise" if state["needs_revision"] else "accept",
        },
        "weighted_total": state["review_total"],
        "aggregated_scores": {
            "correctness_avg": round(c_avg, 2),
            "completeness_avg": round(m_avg, 2),
            "advantage_avg": round(a_avg, 2),
        },
    }

    # 如果接受，标记 final_answer
    if not state["needs_revision"]:
        state["final_answer"] = state.get("draft_answer", "")

    return state


# ============ 并行评审编排 ============

async def parallel_review_node(state: AgentState) -> AgentState:
    """
    并行评审编排节点：使用 asyncio.gather 真正并行调度3个Reviewer

    优势：
    - 3个Reviewer完全并发执行，总耗时 = max(单个Reviewer耗时)
    - Planner决策控制激活哪些Reviewer
    - 错误隔离：单个Reviewer失败使用退路评审
    """
    decisions = state.get("planner_decisions", {})
    active_reviewers = decisions.get("active_reviewers", ["correctness", "completeness", "advantage"])

    if decisions.get("skip_review"):
        # 跳过评审（自我介绍/JD匹配模式）
        state["needs_revision"] = False
        state["final_answer"] = state.get("draft_answer", "")
        state["review_scores"] = {"skipped": 1.0}
        state["review_total"] = 0
        state["quality_report"] = {"mode": "review_skipped"}
        return state

    # 构建并行任务
    tasks = []
    if "correctness" in active_reviewers:
        tasks.append(reviewer_correctness(state))
    if "completeness" in active_reviewers:
        tasks.append(reviewer_completeness(state))
    if "advantage" in active_reviewers:
        tasks.append(reviewer_advantage(state))

    if not tasks:
        state["needs_revision"] = False
        state["final_answer"] = state.get("draft_answer", "")
        return state

    # 真正并行执行！
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time

    # 错误处理
    for i, reviewer_name in enumerate(active_reviewers):
        if i < len(results) and isinstance(results[i], Exception):
            print(f"[ParallelReview] ⚠️ reviewer_{reviewer_name} 失败: {results[i]}")

    # 执行投票
    state = await vote_node(state)

    # 记录性能
    if state.get("quality_report"):
        state["quality_report"]["parallel_elapsed_ms"] = round(elapsed * 1000, 1)
        state["quality_report"]["active_reviewers"] = active_reviewers

    return state


# ============ 退路评审（LLM不可用时的规则化评审）============

def _fallback_correctness_review(state: AgentState) -> Dict[str, Any]:
    """正确性退路评审"""
    answer = state.get("draft_answer", "")
    query = state.get("query", "")

    # 规则化检查
    has_situation = bool(re.search(r'(?:背景|项目|situation|当时|在.*中)', answer, re.IGNORECASE))
    has_task = bool(re.search(r'(?:任务|目标|需要|task|要求|挑战)', answer, re.IGNORECASE))
    has_action = bool(re.search(r'(?:我|负责|实现|设计|开发|采用|使用|action)', answer, re.IGNORECASE))
    has_result = bool(re.search(r'(?:结果|成果|result|提升|降低|优化|达到)', answer, re.IGNORECASE))

    star_score = sum([has_situation, has_task, has_action, has_result]) + 1

    # 检查编造风险的简单判断
    context = state.get("reranked_context", [])
    fabricate_risk = "low"
    if not context and len(answer) > 200:
        fabricate_risk = "high"

    needs_revision = star_score < 4 or fabricate_risk == "high"

    return {
        "needs_revision": needs_revision,
        "scores": {
            "factual_accuracy": 3 if fabricate_risk == "low" else 2,
            "star_structure": star_score,
            "citation_truthfulness": 3 if context else 1,
            "technical_precision": 3,
        },
        "critical_issues": [] if star_score >= 4 else ["STAR结构不完整"],
        "feedback": "请补充完整的STAR结构" if star_score < 4 else "",
        "confidence": 0.7,
    }


def _fallback_completeness_review(state: AgentState) -> Dict[str, Any]:
    """完整性退路评审"""
    answer = state.get("draft_answer", "")
    query = state.get("query", "")

    # 检查问题关键词是否在回答中
    query_keywords = [w for w in re.split(r'[，,。\s]+', query) if len(w) >= 2]
    covered = sum(1 for kw in query_keywords if kw in answer)

    coverage = min(5, max(1, covered))
    needs_revision = coverage < 3

    return {
        "needs_revision": needs_revision,
        "scores": {
            "question_coverage": coverage,
            "key_points": coverage,
            "depth_match": min(5, len(answer) // 100),
            "gap_detection": coverage,
        },
        "missing_aspects": ["回答可能未覆盖问题的关键点"] if coverage < 3 else [],
        "feedback": "请确保回答覆盖了问题的所有方面" if coverage < 3 else "",
        "confidence": 0.6,
    }


def _fallback_advantage_review(state: AgentState) -> Dict[str, Any]:
    """优势展示退路评审"""
    answer = state.get("draft_answer", "")

    # 统计量化指标
    numbers = len(re.findall(r'\d+%|\d+倍|\d+\.\d+|\d+', answer))
    first_person = len(re.findall(r'我\w*', answer))
    unique_indicators = len(re.findall(r'(?:独特|创新|首创|主导|独立|负责)', answer))

    quantitative = min(5, max(1, numbers // 2 + 1))
    personal = min(5, max(1, first_person // 3 + 1))
    uniqueness = min(5, max(1, unique_indicators + 1))

    needs_revision = quantitative < 3 or personal < 3 or uniqueness < 3

    return {
        "needs_revision": needs_revision,
        "scores": {
            "personal_uniqueness": uniqueness,
            "quantitative_showcase": quantitative,
            "first_person_clarity": personal,
            "competitiveness": round((quantitative + personal + uniqueness) / 3),
        },
        "improvement_areas": [
            area for area, score in [
                ("增加量化数据和成果", quantitative),
                ("强化第一人称叙述", personal),
                ("突出个人独特贡献", uniqueness),
            ] if score < 3
        ],
        "feedback": "请加强个人优势和量化成果的展示" if needs_revision else "",
        "confidence": 0.65,
    }


# ============ 辅助函数 ============

def _parse_review_json(raw: str) -> Dict[str, Any]:
    """解析Reviewer的JSON输出"""
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 块
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取花括号内容
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 完全失败
    return {"needs_revision": False, "scores": {}, "feedback": "", "confidence": 0.5}


def _reviewer_label(name: str) -> str:
    """Reviewer中文标签"""
    labels = {
        "correctness": "正确性评审",
        "completeness": "完整性评审",
        "advantage": "优势展示评审",
    }
    return labels.get(name, name)
