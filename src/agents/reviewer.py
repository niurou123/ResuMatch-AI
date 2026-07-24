"""Node 5: QualityReviewer - 5维评分 + 条件修订决策"""
import json
import re
from typing import Dict, Any
from src.agents.state import AgentState
from src.core.llm_client import get_client, Message
from src.core.prompts import build_review_prompt
from src.config import settings


async def quality_reviewer_node(state: AgentState) -> AgentState:
    """
    Node 5: QualityReviewer

    职责：
    1. 5维评分（LLM-as-Judge）
    2. 判断是否需要修订
    3. 生成具体改进意见
    4. 输出 quality_report

    条件边逻辑（在 graph.py 中）：
    - total_score >= MIN_REVIEW_SCORE (20) → END
    - total_score < 20 AND revision_count < MAX_REVISION_ROUNDS (3) → 返回 Writer
    - revision_count >= 3 → END（强制输出）
    """
    answer = state.get("draft_answer", state.get("final_answer", ""))

    if not answer or len(answer) < 20:
        state["review_scores"] = {"overall": 0}
        state["review_total"] = 0
        state["needs_revision"] = True
        state["revision_feedback"] = "回答过短，请提供更详细的内容"
        return state

    revision_count = state.get("revision_count", 0)
    state["revision_count"] = revision_count + 1

    try:
        # LLM 评审
        system_prompt, user_prompt = build_review_prompt(state)

        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        raw = await client.chat_sync(messages, temperature=0.2)

        # 解析 JSON
        review_result = _parse_review_result(raw)

        scores = review_result.get("scores", {})
        total = review_result.get("total", sum(scores.values()) if scores else 0)

        state["review_scores"] = scores
        state["review_total"] = float(total)
        state["quality_report"] = review_result

        # 修订决策
        needs_revision = review_result.get("needs_revision", False)
        if not needs_revision and total < settings.MIN_REVIEW_SCORE:
            needs_revision = True

        if needs_revision and revision_count < settings.MAX_REVISION_ROUNDS:
            state["needs_revision"] = True
            state["revision_feedback"] = review_result.get("feedback", "请改进回答质量")
        else:
            state["needs_revision"] = False
            state["final_answer"] = answer

    except Exception as e:
        # 评审失败时使用规则化退路
        scores = _rule_based_review(answer, state)
        total = sum(scores.values())

        state["review_scores"] = scores
        state["review_total"] = float(total)
        state["quality_report"] = {"scores": scores, "total": total, "method": "rule_based"}

        if total < settings.MIN_REVIEW_SCORE and revision_count < settings.MAX_REVISION_ROUNDS:
            state["needs_revision"] = True
            state["revision_feedback"] = _generate_fallback_feedback(scores)
        else:
            state["needs_revision"] = False
            state["final_answer"] = answer

    return state


def _parse_review_result(raw: str) -> Dict[str, Any]:
    """解析 LLM 评审输出"""
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

    # 完全失败时返回默认值
    return {
        "scores": {"relevance": 3, "star_completeness": 3, "advantage_showcase": 3,
                    "quantitative_density": 3, "authenticity": 3},
        "total": 15,
        "needs_revision": False,
        "feedback": "评审解析失败，使用默认评分",
    }


def _rule_based_review(answer: str, state: AgentState) -> Dict[str, float]:
    """规则化评审退路（不依赖 LLM）"""
    scores = {}

    # 1. 相关性：检查是否包含问题关键词
    query = state.get("query", "")
    query_words = set(query)
    answer_words = set(answer)
    overlap = len(query_words & answer_words)
    scores["relevance"] = min(5, max(1, overlap))

    # 2. STAR 完整性：检查四要素
    star_elements = 0
    if re.search(r'(?:背景|项目|situation|当时|在.*中)', answer, re.IGNORECASE):
        star_elements += 1
    if re.search(r'(?:任务|目标|需要|task|要求|挑战)', answer, re.IGNORECASE):
        star_elements += 1
    if re.search(r'(?:我|负责|实现|设计|开发|采用|使用|action)', answer, re.IGNORECASE):
        star_elements += 1
    if re.search(r'(?:结果|成果|result|提升|降低|优化|达到)', answer, re.IGNORECASE):
        star_elements += 1
    scores["star_completeness"] = min(5, star_elements + 1)

    # 3. 量化密度：数字和百分比
    numbers = len(re.findall(r'\d+%|\d+倍|\d+\.\d+|\d+', answer))
    scores["quantitative_density"] = min(5, max(1, numbers))

    # 4. 优势展示度：第一人称叙述 + 独特贡献
    first_person = len(re.findall(r'我\w*', answer))
    scores["advantage_showcase"] = min(5, max(1, first_person // 2 + 1))

    # 5. 真实性：是否引用上下文中的具体信息
    context_items = len(state.get("reranked_context", []))
    ref_found = 0
    for ctx in state.get("reranked_context", [])[:5]:
        content_words = set(ctx.get("content", "")[:50])
        if len(content_words & answer_words) > 3:
            ref_found += 1
    scores["authenticity"] = min(5, max(1, ref_found + (1 if context_items > 0 else 0)))

    return scores


def _generate_fallback_feedback(scores: Dict[str, float]) -> str:
    """生成规则化的改进意见"""
    feedback_parts = []

    dims_cn = {
        "relevance": "回答与问题的相关性",
        "star_completeness": "STAR结构完整性",
        "advantage_showcase": "个人优势展示",
        "quantitative_density": "量化数据密度",
        "authenticity": "回答真实性和引用准确性",
    }

    for dim, score in scores.items():
        if score < 3:
            cn_name = dims_cn.get(dim, dim)
            feedback_parts.append(f"请加强{cn_name}")

    if not feedback_parts:
        return "回答基本符合要求，可以进一步优化细节和量化数据"

    return "；".join(feedback_parts) + "。"
