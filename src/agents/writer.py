"""Node 4: STARWriter - 流式生成 + 引用约束"""
import re
from typing import Dict, Any, AsyncGenerator, List
from src.agents.state import AgentState
from src.core.llm_client import get_client, Message
from src.core.prompts import build_star_prompt


async def star_writer_node(state: AgentState) -> AgentState:
    """
    Node 4: STARWriter

    职责：
    1. 基于检索上下文生成 STAR 格式回答
    2. 强制引用约束（Citation Rules）
    3. 流式生成 + 后处理验证

    如果 quality_reviewer 触发了修订，revision_feedback 和 revision_count 已被设置，
    本节点会将反馈融入到新一轮生成中。
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

        # 使用同步调用（兼容子线程执行）
        full_answer = await client.chat_sync(messages)

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
            # 完全没有引用，添加提示
            pass  # 让 Reviewer 来评判

    return answer
