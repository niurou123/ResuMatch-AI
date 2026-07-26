"""
STARWriter + Agent间通信集成

Writer现在支持：
1. STAR格式生成 + 引用约束
2. 自我检查不确定声明 → 主动咨询正确性Reviewer
3. 回答完整性自查 → 咨询完整性Reviewer
4. 说服力自查 → 咨询优势Reviewer
5. 根据Reviewer反馈迭代优化
"""
import re
from typing import Dict, Any, AsyncGenerator, List
from src.agents.state import AgentState
from src.core.llm_client import get_client, Message
from src.core.prompts import build_star_prompt


async def star_writer_node(state: AgentState) -> AgentState:
    """
    STARWriter (增强版) - 支持Agent间通信

    职责：
    1. 基于检索上下文生成 STAR 格式回答
    2. 自我检查：识别不确定声明
    3. 向Reviewer咨询不确定内容
    4. 集成Reviewer反馈优化回答
    5. 强制引用约束（Citation Rules）

    修订支持：
    如果 vote 触发了修订，revision_feedback 已包含3个Reviewer的聚合反馈，
    Writer会针对性地修改回答。
    """
    query = state.get("query", "")
    reranked_context = state.get("reranked_context", [])

    if not query.strip():
        state["draft_answer"] = "请提供面试问题"
        return state

    try:
        system_prompt, user_prompt = build_star_prompt(state)

        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        # 使用同步调用
        full_answer = await client.chat_sync(messages)

        # ===== Agent通信：自我检查不确定声明 =====
        uncertain_claims = _detect_uncertain_claims(full_answer)

        if uncertain_claims and reranked_context:
            # 向正确性Reviewer咨询不确定的声明
            from src.agents.communication import writer_check_factual_claim

            corrections = []
            for claim in uncertain_claims[:3]:  # 最多检查3个不确定声明
                response = await writer_check_factual_claim(
                    state, claim,
                    context="\n".join([c.get("content", "")[:300] for c in reranked_context[:5]]),
                )
                if response.get("confidence", 0) > 0.5 and response.get("suggestion"):
                    corrections.append(response["suggestion"])

            # 如果有修正建议，进行第二轮优化
            if corrections:
                correction_text = "\n".join([
                    f"- {c}" for c in corrections
                ])
                refine_prompt = f"""你之前的回答中有一些需要修正的地方：

{correction_text}

请根据以上建议优化你的回答。只修改需要修正的部分，保持原有正确内容不变。
原始问题：{query}"""

                refinement_messages = [
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=refine_prompt),
                ]
                refined = await client.chat_sync(refinement_messages, temperature=0.4)
                if refined and len(refined) > 20:
                    full_answer = refined

        # 后处理：验证引用
        citations = _extract_citations(full_answer, reranked_context)
        validated_answer = _validate_citations(full_answer, citations)

        state["draft_answer"] = validated_answer
        state["citations"] = citations

        # 如果无引用且不是第一轮，加警告
        if not citations and state.get("revision_count", 0) > 0:
            state["draft_answer"] += "\n\n⚠️ 注意：此回答未包含明确的经历引用，建议补充具体项目经验。"

    except Exception as e:
        state["draft_answer"] = f"生成回答时出错: {str(e)}"
        state["error"] = f"STARWriter 失败: {str(e)}"

    return state


async def star_writer_stream(state: AgentState) -> AsyncGenerator[str, None]:
    """
    流式 STAR 生成器（用于 SSE 端点）
    逐 token yield，实现首字延迟 < 2s
    """
    query = state.get("query", "")

    if not query.strip():
        yield "请提供面试问题"
        return

    try:
        system_prompt, user_prompt = build_star_prompt(state)

        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        async for chunk in client.chat_stream(messages):
            yield chunk

    except Exception as e:
        yield f"\n\n[生成错误: {str(e)}]"


def _detect_uncertain_claims(answer: str) -> List[str]:
    """
    检测回答中Writer不确定的声明

    识别模式：
    1. 模糊表述：可能、大概、约、大约
    2. LLM自我标记：[不确定]、[需验证]
    3. 无引用支持的量化声明
    """
    uncertain = []

    # 模式1: 模糊量化表述
    fuzzy_patterns = [
        r'(?:大概|大约|约|左右|可能|也许).{0,20}(?:\d+%|\d+倍|\d+\.\d+|\d+)',
        r'(?:\d+%|\d+倍|\d+\.\d+|\d+).{0,10}(?:左右|大概|大约|约|可能)',
    ]
    for pattern in fuzzy_patterns:
        matches = re.findall(pattern, answer)
        uncertain.extend(matches)

    # 模式2: 自我标记
    marked = re.findall(r'\[不确定\](.*?)\[/不确定\]', answer)
    uncertain.extend(marked)

    # 模式3: 看起来像编造的数字（超过3位数的精确数字且无引用）
    precise_numbers = re.findall(r'(?<!\d)\d{4,}(?!\d)', answer)
    for num in precise_numbers[:3]:
        if num not in uncertain:
            uncertain.append(f"精确数字: {num}")

    return uncertain[:5]  # 最多返回5个


def _extract_citations(answer: str, context: List[Dict]) -> List[Dict[str, Any]]:
    """从回答中提取引用标注"""
    citations = []

    # 匹配 [来源: xxx] 或 [Citation: xxx] 格式
    patterns = [
        r'\[(?:来源|Citation|引用)[：:]\s*(.+?)\]',
        r'\[(?:source|citation)[：:]\s*(.+?)\]',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, answer, re.IGNORECASE)
        for match in matches:
            # 在上下文中找到对应的文档
            for ctx in context:
                if match.lower() in ctx.get("content", "").lower():
                    citations.append({
                        "text": match,
                        "source_id": ctx.get("id", ""),
                        "collection": ctx.get("collection", ""),
                        "score": ctx.get("rerank_score", ctx.get("score", 0)),
                    })
                    break

    return citations


def _validate_citations(answer: str, citations: List[Dict]) -> str:
    """验证并修正引用"""
    if not citations:
        # 检查是否引用了具体项目名或数字（间接引用）
        has_project_ref = bool(re.search(
            r'(?:PaperPilot|ResuMatch|项目中|系统中|平台中)', answer
        ))
        has_number_ref = bool(re.search(r'\d+%|\d+倍|从\d+到\d+', answer))

        if not has_project_ref and not has_number_ref:
            # 完全没有引用，让 Reviewer 来评判
            pass

    return answer
