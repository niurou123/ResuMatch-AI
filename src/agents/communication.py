"""
Agent间通信模块 - 实现 Writer ↔ Reviewer 双向通信

核心机制：
1. Writer生成回答时，可以标记"不确定"的部分
2. Writer发起 query → Reviewer 回复 answer（通过 state 传递）
3. 支持同步通信（等待Reviewer回复后继续生成）
4. 支持异步通信（Writer继续生成，Reviewer反馈用于下一轮修订）

通信协议：
  Writer → Reviewer:  {"type": "query", "target": "correctness|completeness|advantage",
                        "question": "...", "context": "..."}
  Reviewer → Writer: {"type": "response", "source": "correctness|...",
                       "answer": "...", "confidence": 0.85,
                       "suggestion": "..."}
"""
import asyncio
from typing import Dict, Any, List, Optional
from src.agents.state import AgentState
from src.core.llm_client import get_client, Message


# ============ 通信消息类型 ============

class AgentMessage:
    """Agent间通信消息"""

    @staticmethod
    def create_query(target: str, question: str, context: str = "") -> Dict[str, Any]:
        """Writer创建查询消息"""
        return {
            "type": "query",
            "source": "writer",
            "target": target,
            "question": question,
            "context": context,
        }

    @staticmethod
    def create_response(source: str, answer: str, confidence: float = 0.5,
                        suggestion: str = "") -> Dict[str, Any]:
        """Reviewer创建回复消息"""
        return {
            "type": "response",
            "source": source,
            "answer": answer,
            "confidence": confidence,
            "suggestion": suggestion,
        }


# ============ Writer端：发起咨询 ============

async def writer_consult_reviewer(
    state: AgentState,
    target: str,
    question: str,
    context: str = "",
) -> Dict[str, Any]:
    """
    Writer向指定Reviewer发起咨询

    Args:
        state: 当前Agent状态
        target: 目标Reviewer (correctness/completeness/advantage)
        question: 咨询的问题
        context: 相关上下文

    Returns:
        Reviewer的回复消息
    """
    query_msg = AgentMessage.create_query(target, question, context)

    # 记录查询
    writer_queries = state.get("writer_queries", [])
    writer_queries.append(query_msg)
    state["writer_queries"] = writer_queries

    # 根据目标调用对应的Reviewer进行微咨询
    if target == "correctness":
        response = await _consult_correctness(state, question, context)
    elif target == "completeness":
        response = await _consult_completeness(state, question, context)
    elif target == "advantage":
        response = await _consult_advantage(state, question, context)
    else:
        response = AgentMessage.create_response(
            "unknown",
            "无法识别目标Reviewer",
            confidence=0.0,
            suggestion="请指定正确性(correctness)、完整性(completeness)或优势(advantage)评审",
        )

    # 记录回复
    writer_queries.append(response)
    state["writer_queries"] = writer_queries

    return response


async def writer_check_factual_claim(
    state: AgentState,
    claim: str,
    context: str = "",
) -> Dict[str, Any]:
    """
    Writer快速检查一个事实性声明是否可用于回答

    用于生成过程中验证数据真实性
    """
    question = f"请验证以下陈述是否可以使用在回答中（基于简历素材）：\n{claim}"
    return await writer_consult_reviewer(state, "correctness", question, context)


async def writer_check_completeness(
    state: AgentState,
    answer_snippet: str,
    query: str = "",
) -> Dict[str, Any]:
    """
    Writer检查当前回答片段是否覆盖了问题的关键方面
    """
    question = f"请检查以下回答片段是否覆盖了问题的关键方面：\n问题：{query}\n回答片段：{answer_snippet}"
    return await writer_consult_reviewer(state, "completeness", question)


async def writer_check_advantage_impact(
    state: AgentState,
    answer_snippet: str,
) -> Dict[str, Any]:
    """
    Writer检查当前表述是否足够有说服力
    """
    question = f"请评估以下表述的说服力和竞争力：\n{answer_snippet}\n如果不够有力，请建议如何强化。"
    return await writer_consult_reviewer(state, "advantage", question)


# ============ Reviewer端：响应咨询 ============

async def _consult_correctness(state: AgentState, question: str, context: str) -> Dict[str, Any]:
    """正确性Reviewer的微咨询（轻量级，非完整评审）"""
    draft = state.get("draft_answer", "")
    ctx_text = _format_context_simple(state)

    system_prompt = """你是一个快速事实检查器。根据简历素材，简短回答以下咨询问题。
只返回JSON: {"answer": "...", "confidence": 0.0-1.0, "suggestion": "..."}"""

    user_prompt = f"""简历素材：
{ctx_text[:2000]}

当前回答草稿：
{draft[:1000]}

咨询问题：
{question}

请简短回答并给出建议。"""

    try:
        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        raw = await client.chat_sync(messages, temperature=0.2, max_tokens=500)

        import json, re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return AgentMessage.create_response(
                "correctness",
                data.get("answer", raw),
                data.get("confidence", 0.5),
                data.get("suggestion", ""),
            )
    except Exception:
        pass

    return AgentMessage.create_response(
        "correctness",
        "无法验证（服务暂时不可用）",
        confidence=0.0,
        suggestion="建议基于简历素材自行判断",
    )


async def _consult_completeness(state: AgentState, question: str, context: str) -> Dict[str, Any]:
    """完整性Reviewer的微咨询"""
    draft = state.get("draft_answer", "")

    system_prompt = """你是一个快速完整性检查器。简短判断回答是否遗漏了关键信息。
只返回JSON: {"answer": "...", "confidence": 0.0-1.0, "suggestion": "..."}"""

    user_prompt = f"""原始问题：
{state.get('query', '')}

当前回答草稿：
{draft[:1000]}

咨询问题：
{question}

请简短回答。"""

    try:
        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        raw = await client.chat_sync(messages, temperature=0.2, max_tokens=500)

        import json, re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return AgentMessage.create_response(
                "completeness",
                data.get("answer", raw),
                data.get("confidence", 0.5),
                data.get("suggestion", ""),
            )
    except Exception:
        pass

    return AgentMessage.create_response(
        "completeness",
        "无法检查（服务暂时不可用）",
        confidence=0.0,
        suggestion="建议对照问题要点逐一检查",
    )


async def _consult_advantage(state: AgentState, question: str, context: str) -> Dict[str, Any]:
    """优势展示Reviewer的微咨询"""
    draft = state.get("draft_answer", "")

    system_prompt = """你是一个快速竞争力评估器。简短判断表述是否有足够的说服力。
只返回JSON: {"answer": "...", "confidence": 0.0-1.0, "suggestion": "..."}"""

    user_prompt = f"""当前回答：
{draft[:1000]}

咨询问题：
{question}

请简短回答并提供建议。"""

    try:
        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        raw = await client.chat_sync(messages, temperature=0.2, max_tokens=500)

        import json, re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return AgentMessage.create_response(
                "advantage",
                data.get("answer", raw),
                data.get("confidence", 0.5),
                data.get("suggestion", ""),
            )
    except Exception:
        pass

    return AgentMessage.create_response(
        "advantage",
        "无法评估（服务暂时不可用）",
        confidence=0.0,
        suggestion="建议使用具体数字和第一人称强化表述",
    )


# ============ 辅助 ============

def _format_context_simple(state: AgentState) -> str:
    """简单地格式化上下文"""
    ctx = state.get("reranked_context", [])
    if not ctx:
        ctx = (
            state.get("retrieved_skills", []) +
            state.get("retrieved_projects", []) +
            state.get("retrieved_achievements", [])
        )

    lines = []
    for item in ctx[:10]:
        coll = item.get("collection", "")
        content = item.get("content", "")[:200]
        meta = item.get("metadata", {})
        name = meta.get("name", "")
        lines.append(f"[{coll}] {name}: {content}")

    return "\n".join(lines) if lines else "无可用素材"


def get_communication_summary(state: AgentState) -> str:
    """获取Agent间通信摘要（用于调试）"""
    queries = state.get("writer_queries", [])
    if not queries:
        return "无Agent间通信记录"

    lines = ["📡 Agent间通信记录:"]
    for i, msg in enumerate(queries):
        msg_type = msg.get("type", "unknown")
        source = msg.get("source", "?")
        target = msg.get("target", "?")
        question = msg.get("question", msg.get("answer", ""))[:100]
        confidence = msg.get("confidence", "N/A")

        if msg_type == "query":
            lines.append(f"  {i+1}. 📤 Writer → {target}: {question}")
        else:
            lines.append(f"  {i+1}. 📥 {source} → Writer [置信度: {confidence}]: {question}")

    return "\n".join(lines)
