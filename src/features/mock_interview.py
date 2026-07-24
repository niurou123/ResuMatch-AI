"""模拟面试模式 - 多轮追问引擎"""
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from src.core.llm_client import get_client, Message


@dataclass
class MockSession:
    """模拟面试会话"""
    session_id: str
    max_rounds: int = 5
    current_round: int = 0
    focus_areas: List[str] = field(default_factory=list)
    difficulty: str = "intermediate"
    history: List[Dict[str, str]] = field(default_factory=list)
    scores_history: List[Dict[str, float]] = field(default_factory=list)

    # 追问策略
    question_pool: List[str] = field(default_factory=list)
    covered_topics: set = field(default_factory=set)


class MockInterviewEngine:
    """模拟面试引擎"""

    # 默认面试题库（按类别）
    DEFAULT_QUESTIONS = {
        "technical": [
            "请详细解释一下你在项目中使用的主要技术架构",
            "你在项目中遇到的最大技术挑战是什么？如何解决的？",
            "描述一次你做出的重要技术决策及其影响",
            "你如何保证代码质量和系统稳定性？",
            "请介绍一个你从零开始搭建的项目",
        ],
        "behavioral": [
            "描述一次你与团队成员产生分歧的经历，你是如何处理的？",
            "你如何平衡多个项目的优先级？",
            "请举一个你主动承担额外责任的例子",
            "描述一次你从失败中学到的教训",
            "你如何保持对新技术的持续学习？",
        ],
        "project": [
            "请深入介绍一个你认为最有代表性的项目",
            "在这个项目中，哪些决策如果重来你会做出不同选择？",
            "你的项目中哪个部分是你最引以为豪的？",
            "你如何衡量项目的成功？",
            "项目中最让你意外的问题是什么？",
        ],
        "career": [
            "你为什么选择这个职业方向？",
            "你对未来3-5年的职业规划是什么？",
            "你认为自己最大的优势是什么？",
            "你觉得自己在哪些方面还需要提升？",
            "你为什么想加入我们公司？",
        ],
    }

    def __init__(self):
        self.client = get_client()
        self._sessions: Dict[str, MockSession] = {}

    def start_session(
        self, focus_areas: List[str] = None,
        difficulty: str = "intermediate", max_rounds: int = 5
    ) -> MockSession:
        """开始新的模拟面试会话"""
        session_id = str(uuid.uuid4())[:8]
        session = MockSession(
            session_id=session_id,
            max_rounds=max_rounds,
            focus_areas=focus_areas or [],
            difficulty=difficulty,
        )
        self._sessions[session_id] = session
        return session

    async def get_next_question(self, session_id: str) -> Optional[str]:
        """获取下一个面试问题"""
        session = self._sessions.get(session_id)
        if not session:
            return None

        session.current_round += 1

        if session.current_round > session.max_rounds:
            return None

        # 第一轮：开场问题
        if session.current_round == 1:
            return self._get_opening_question(session)

        # 后续轮次：基于上下文的追问
        return await self._generate_followup(session)

    async def process_answer(
        self, session_id: str, answer: str
    ) -> Dict[str, Any]:
        """处理候选人的回答"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "会话不存在"}

        # 记录回答
        session.history.append({
            "round": session.current_round,
            "answer": answer,
        })

        # 简单评估（可选：集成 LLM Judge）
        feedback = await self._quick_feedback(answer, session)

        is_last = session.current_round >= session.max_rounds

        return {
            "round": session.current_round,
            "feedback": feedback,
            "is_last": is_last,
        }

    async def generate_summary(self, session_id: str) -> str:
        """生成面试总结"""
        session = self._sessions.get(session_id)
        if not session or not session.history:
            return "无法生成总结"

        history_text = "\n".join([
            f"Q{h['round']}: {h.get('question', '')}\nA: {h['answer'][:300]}"
            for h in session.history
        ])

        prompt = f"""请根据以下模拟面试记录，生成一份简洁的面试表现总结。

## 面试记录
{history_text}

请从以下方面总结（200字以内）：
1. 整体表现评价
2. 主要优势
3. 需要改进的地方
4. 准备建议"""

        messages = [Message(role="user", content=prompt)]
        return await self.client.chat_sync(messages, temperature=0.5, max_tokens=400)

    def get_session(self, session_id: str) -> Optional[MockSession]:
        """获取会话"""
        return self._sessions.get(session_id)

    # ===== 私有方法 =====

    def _get_opening_question(self, session: MockSession) -> str:
        """生成开场问题"""
        if session.focus_areas:
            areas = "、".join(session.focus_areas)
            return f"你好！感谢参加今天的面试。我看到你的背景涉及{areas}领域。请先简要介绍一下你自己，特别是与这些领域相关的经验。"
        return "你好！请先做一个简短的自我介绍，让我了解一下你的背景和核心技能。"

    async def _generate_followup(self, session: MockSession) -> str:
        """基于上下文生成追问"""
        # 提取最近一轮回答的关键词
        last_answer = ""
        if session.history:
            last_answer = session.history[-1].get("answer", "")

        # 简单的追问策略
        round_num = session.current_round
        categories = ["technical", "behavioral", "project", "career"]
        category = categories[(round_num - 1) % len(categories)]

        questions = self.DEFAULT_QUESTIONS.get(category, self.DEFAULT_QUESTIONS["technical"])
        available = [q for q in questions if q not in session.covered_topics]
        if not available:
            available = questions

        question = available[0]
        session.covered_topics.add(question)
        return question

    async def _quick_feedback(self, answer: str, session: MockSession) -> Dict[str, Any]:
        """快速反馈（轻量级）"""
        # 简单的启发式反馈
        feedback = {}

        # 长度检查
        if len(answer) < 50:
            feedback["length"] = "回答偏短，建议展开更多细节"
        elif len(answer) > 1000:
            feedback["length"] = "回答较长，注意保持精炼"

        # STAR 结构检查
        has_context = any(kw in answer for kw in ["当时", "在", "项目", "背景", "之前"])
        has_action = any(kw in answer for kw in ["我", "负责", "实现", "做了", "采用"])
        has_result = any(kw in answer for kw in ["结果", "成果", "提升", "降低", "优化", "达到"])

        star_score = sum([has_context, has_action, has_result])
        if star_score < 2:
            feedback["structure"] = "建议使用STAR结构（背景-任务-行动-结果）"

        return feedback
