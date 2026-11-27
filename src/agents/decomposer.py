"""复合问题分解与子问题并行作答（fan-out / fan-in）

为什么需要这条链路
------------------
单条链路回答“比较两个项目的技术选型差异，并说明各自的取舍”这类复合问题时，容易只
覆盖其中一两个方面。多 Agent 的真正优势在于：把复合问题拆成互不重叠的子问题，
**并行**为每个子问题取证与作答，最后整合——这样“方面覆盖率”不再取决于一次生成是否
恰好想到全部要点。

三个节点
--------
decomposition_node  ：判定是否复合问题 → 由 LLM 拆成 2~4 个子问题（规则切分兜底）
sub_answer_node     ：并发为每个子问题检索证据并生成简短答案（asyncio.gather）
synthesize_node     ：把子答案整合为一段 STAR 结构总答，并回填检索素材供后续修订复用

设计取舍
--------
- 只在**复合问题**上启用：简单问题走原链路，避免为复杂而复杂、也避免无谓延迟
- fast 模式不启用：该模式的定位就是低延迟
- 子问题上限 4 个：超过则证据过于分散，收益递减
- 任一子问题失败不影响整体：丢弃该子问题并在总答中说明缺失，符合项目的错误隔离原则
"""
import asyncio
import json
import re
from typing import Any, Dict, List, Literal

from src.agents.state import AgentState
from src.core.llm_client import get_client, Message
from src.rag.vector_store import get_vector_store

MAX_SUB_QUESTIONS = 4
SUB_TOP_K = 3
SUB_COLLECTIONS = ("projects", "skills", "achievements", "education")
MAX_EVIDENCE_ROUNDS = 2      # 首轮 + 最多一轮补充检索
MIN_ANSWER_LEN = 30          # 子答案短于此视为"没答出来"，触发补充检索

# 复合问题的判定线索：出现"分别/各自/对比/差异/以及"等并列或比较表述
COMPOSITE_MARKERS = (
    "分别", "各自", "对比", "比较", "区别", "差异", "取舍", "优缺点",
    "以及", "同时", "两方面", "三方面", "哪些方面", "分别是", "各有什么",
)

SPLIT_SYSTEM = (
    "你是面试问题的结构化拆解器。任务：把一个复合面试问题拆成 2~4 个互相独立、"
    "合起来能完整覆盖原问题的子问题。要求：\n"
    "1. 子问题必须能各自独立回答，不要互相包含\n"
    "2. 子问题要具体，避免“请详细介绍”这类空泛表述\n"
    "3. 只输出 JSON 数组，例如 [\"子问题1\", \"子问题2\"]，不要任何解释\n"
    "4. 若问题本身不可拆解，输出空数组 []"
)

SYNTH_SYSTEM = (
    "你是面试回答整合器。下面给出原始问题与若干个子问题的独立答案（均已基于简历素材）。"
    "请把它们整合成一段连贯的面试回答，要求：\n"
    "1. 严格按四段式输出，标签原样保留："
    "**情境（Situation）**、**任务（Task）**、**行动（Action）**、**结果（Result）**\n"
    "2. 必须覆盖每个子问题给出的要点，不得遗漏；同一事实不要重复叙述\n"
    "3. 只能使用子答案中出现的事实与数字，不得新增或改写数字\n"
    "4. 全文第一人称，400 字以内"
)


def is_composite(question: str) -> bool:
    """规则判定是否为复合问题（成本为零，先过一遍）"""
    q = (question or "").strip()
    if len(q) < 18:
        return False
    hit = sum(1 for m in COMPOSITE_MARKERS if m in q)
    # 出现两个及以上并列/比较线索，或出现"分别"且句子较长，判为复合
    return hit >= 2 or ("分别" in q and len(q) >= 25)


def _rule_split(question: str) -> List[str]:
    """规则切分兜底：按并列连接词与顿号切开，保留有意义的片段"""
    parts = re.split(r"[；;。]|，?以及|，?同时|，?并且|，?而", question)
    subs = [p.strip(" ，,、") for p in parts if len(p.strip(" ，,、")) >= 6]
    if len(subs) <= 1:
        return []
    return subs[:MAX_SUB_QUESTIONS]


async def _llm_split(question: str) -> List[str]:
    """由 LLM 拆解子问题；失败返回空列表交由规则兜底"""
    try:
        client = get_client()
        resp = await client.chat(
            [Message(role="system", content=SPLIT_SYSTEM),
             Message(role="user", content=f"面试问题：{question}")],
            temperature=0.2,
        )
        text = (resp.content or "").strip()
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            return []
        arr = json.loads(m.group(0))
        subs = [str(x).strip() for x in arr if str(x).strip()]
        return subs[:MAX_SUB_QUESTIONS]
    except Exception:
        return []


async def decomposition_node(state: AgentState) -> AgentState:
    """判定 + 拆解子问题（不复合则原样返回，链路自动回落到原路径）"""
    query = state.get("query", "")
    state.setdefault("sub_questions", [])
    state.setdefault("sub_answers", [])
    state["decomposition_used"] = False

    if not is_composite(query):
        return state

    subs = await _llm_split(query)
    source = "llm"
    if not subs:
        subs = _rule_split(query)
        source = "rule"
    if not subs:
        return state

    state["sub_questions"] = subs
    state["decomposition_used"] = True
    state["decomposition_source"] = source
    state["evidence_rounds"] = 1
    state["supplement_queries"] = {}
    return state


async def _answer_one(client, vs, sub_q: str, index: int) -> Dict[str, Any]:
    """单个子问题：多集合检索 → 生成简短答案"""
    contexts: List[Dict[str, Any]] = []
    for coll in SUB_COLLECTIONS:
        try:
            hits = vs.search(sub_q, coll, top_k=SUB_TOP_K)
            contexts.extend(hits or [])
        except Exception:
            continue
    contexts.sort(key=lambda c: float(c.get("score") or 0), reverse=True)
    top = contexts[:8]

    if not top:
        return {"index": index, "question": sub_q, "answer": "", "n_ctx": 0}

    materials = "\n".join(
        f"- {str(c.get('content', ''))[:280]}" for c in top if c.get("content")
    )
    user = (
        f"【简历素材】\n{materials}\n\n"
        f"【子问题】\n{sub_q}\n\n"
        "请仅依据上述素材回答，120 字以内，只陈述事实，不编造数字；"
        "素材不足时直接说明缺少哪部分信息。"
    )
    try:
        resp = await client.chat(
            [Message(role="system", content="你是严谨的面试回答助手，只依据给定素材作答。"),
             Message(role="user", content=user)],
            temperature=0.3,
        )
        answer = (resp.content or "").strip()
    except Exception as ex:
        return {"index": index, "question": sub_q, "answer": "", "n_ctx": len(top),
                "error": str(ex)[:120]}
    return {"index": index, "question": sub_q, "answer": answer,
            "n_ctx": len(top), "contexts": top}


SUPPLEMENT_SYSTEM = (
    "你是证据充分性评审官。下面给出原始问题、拆解出的子问题及每个子问题当前的答案。"
    "请判断哪些子问题仍然缺少有效证据或答案过于空泛，并为这些子问题各生成一条更具体的补充检索查询。"
    "只输出 JSON 对象，不要解释："
    '{"ok": true/false, "supplement": {"子问题原文": "补充检索词"}}。'
    "若所有子问题都已充分作答，则 ok 为 true、supplement 为空对象。"
)


def _answer_ok(rec: Dict[str, Any] | None) -> bool:
    """子答案是否可接受：内容足够长且确实检索到了证据"""
    if not rec:
        return False
    ans = (rec.get("answer") or "").strip()
    return len(ans) >= MIN_ANSWER_LEN and int(rec.get("n_ctx") or 0) > 0


async def sub_answer_node(state: AgentState) -> AgentState:
    """并发为每个子问题取证并作答（真正的 fan-out）

    支持证据补充轮次：只处理"仍缺失"的子问题，并把补充查询词并入检索词，
    已有有效答案的子问题不重复消耗调用。
    """
    subs = state.get("sub_questions") or []
    if not subs:
        state["sub_answers"] = []
        return state

    try:
        vs = get_vector_store()
    except Exception as ex:
        state.setdefault("sub_answers", [])
        state["error"] = f"子问题检索不可用: {str(ex)[:80]}"
        return state

    client = get_client()
    prev = {a.get("question"): a for a in (state.get("sub_answers") or [])}
    supplement = state.get("supplement_queries") or {}
    round_no = int(state.get("evidence_rounds") or 1)

    targets = []
    for i, sq in enumerate(subs):
        if _answer_ok(prev.get(sq)):
            continue
        extra = (supplement.get(sq) or "").strip()
        query = f"{sq} {extra}".strip() if extra else sq
        targets.append((i, sq, query))

    if not targets:
        state["sub_answers"] = [prev[sq] for sq in subs if sq in prev]
        return state

    tasks = [_answer_one(client, vs, q, i) for i, sq, q in targets]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged, ctx_new = dict(prev), []
    for (i, sq, _q), r in zip(targets, results):
        if isinstance(r, Exception):
            continue
        merged[sq] = {k: v for k, v in r.items() if k != "contexts"}
        merged[sq]["round"] = round_no
        ctx_new.extend(r.get("contexts") or [])

    state["sub_answers"] = [merged[sq] for sq in subs if sq in merged]
    # 回填素材：若后续评审要求修订，Writer 仍有可用上下文
    if ctx_new:
        state["reranked_context"] = ((state.get("reranked_context") or []) + ctx_new)[:12]
    return state


async def synthesize_node(state: AgentState) -> AgentState:
    """把子答案整合为 STAR 总答（fan-in）"""
    subs = state.get("sub_answers") or []
    ok = [s for s in subs if (s.get("answer") or "").strip()]
    if not ok:
        # 全部失败：不给空答案，明确说明并交回原链路由评审兜底
        state["final_answer"] = ""
        derived = ""
    else:
        body = "\n\n".join(
            f"【子问题{i+1}】{s.get('question','')}\n参考答案：{s.get('answer','')}"
            for i, s in enumerate(ok)
        )
        prompt = (
            f"【原始问题】\n{state.get('query','')}\n\n"
            f"【子问题及独立答案】\n{body}\n\n"
            "请整合为一段连贯的面试回答。"
        )
        try:
            client = get_client()
            resp = await client.chat(
                [Message(role="system", content=SYNTH_SYSTEM),
                 Message(role="user", content=prompt)],
                temperature=0.3,
            )
            derived = (resp.content or "").strip()
        except Exception as ex:
            derived = ""
            state["error"] = f"整合失败: {str(ex)[:80]}"

    state["draft_answer"] = derived
    state["final_answer"] = derived
    state["decomposition_stats"] = {
        "n_sub_questions": len(subs),
        "n_answered": len(ok),
        "source": state.get("decomposition_source", ""),
    }
    return state

async def evidence_gate_node(state: AgentState) -> AgentState:
    """证据充分性闸门（Self-RAG 式迭代检索的判定节点）

    规则先判：若有子问题没答出来且未达轮次上限，则由 LLM 生成补充检索查询，
    交由 sub_answer 再跑一轮；否则放行到综合节点。
    目的：小语料下首轮检索容易漏证据，用一次定向补充检索把它补回来。
    """
    subs = state.get("sub_questions") or []
    answers = {a.get("question"): a for a in (state.get("sub_answers") or [])}
    missing = [sq for sq in subs if not _answer_ok(answers.get(sq))]
    rounds = int(state.get("evidence_rounds") or 1)
    state["supplement_queries"] = {}

    if not missing or rounds >= MAX_EVIDENCE_ROUNDS:
        state["evidence_sufficiency"] = {"missing": missing, "rounds": rounds,
                                         "ok": not missing}
        return state

    supplement: Dict[str, str] = {}
    try:
        client = get_client()
        detail = "\n".join(
            f"- 子问题：{sq}\n  当前答案：{((answers.get(sq) or {}).get('answer') or '（无）')[:120]}"
            for sq in subs
        )
        resp = await client.chat(
            [Message(role="system", content=SUPPLEMENT_SYSTEM),
             Message(role="user",
                     content=f"【原始问题】{state.get('query','')}\n\n【子问题与当前答案】\n{detail}")],
            temperature=0.2,
        )
        m = re.search(r"\{.*\}", resp.content or "", re.S)
        if m:
            data = json.loads(m.group(0))
            if not data.get("ok"):
                supplement = {k: str(v) for k, v in (data.get("supplement") or {}).items() if v}
    except Exception:
        supplement = {}

    if not supplement:
        # 兜底：固定改写模式，保证一定有一次定向补充检索
        supplement = {sq: "具体做法 技术细节 量化结果" for sq in missing}

    state["supplement_queries"] = supplement
    state["evidence_rounds"] = rounds + 1
    state["evidence_sufficiency"] = {"missing": missing, "rounds": rounds,
                                     "ok": False, "supplement": supplement}
    return state


def should_supplement(state: AgentState) -> Literal["supplement", "synthesize"]:
    """闸门之后的分流：需要补充则回到子问题节点再跑一轮，否则进入综合"""
    if state.get("supplement_queries"):
        return "supplement"
    return "synthesize"
