"""LLM-as-Judge 自动化评测管道"""
import json
from typing import Dict, Any, List
from dataclasses import dataclass, field
from src.core.llm_client import get_client, Message


@dataclass
class JudgeResult:
    """LLM 评测结果"""
    scores: Dict[str, float] = field(default_factory=dict)
    total: float = 0.0
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    needs_revision: bool = False
    feedback: str = ""
    raw_response: str = ""


class LLMJudge:
    """
    LLM 作为评委的自动化评测管道

    用途：
    1. 建立回答质量基线
    2. Prompt 迭代时量化对比
    3. 在线质量监控
    """

    SCORING_RUBRIC = """你是一个严格的面试质量评审专家。

请对以下面试回答评分（每项 1-5 分，JSON 格式输出）：

评分维度：
1. relevance (1-5): 回答是否紧扣问题核心，没有偏题
2. star_completeness (1-5): S/T/A/R 四要素是否完整清晰
3. advantage_showcase (1-5): 是否充分展示个人独特优势和能力
4. quantitative_density (1-5): 是否包含具体数字、百分比、可衡量成果
5. authenticity (1-5): 回答是否基于真实经历，引用是否与简历匹配

严格返回 JSON 格式（不要其他文字）：
{
    "scores": {
        "relevance": 4,
        "star_completeness": 5,
        "advantage_showcase": 3,
        "quantitative_density": 4,
        "authenticity": 5
    },
    "total": 21,
    "strengths": ["STAR结构完整清晰", "引用了具体的量化成果"],
    "weaknesses": ["可以更突出个人在项目中的独特贡献"],
    "needs_revision": false,
    "feedback": ""
}"""

    def __init__(self):
        self.client = get_client()

    async def evaluate(
        self, question: str, answer: str, profile_summary: str = "",
        context: List[Dict] = None
    ) -> JudgeResult:
        """
        评测单个面试回答

        Args:
            question: 面试问题
            answer: 候选人回答
            profile_summary: 候选人背景摘要
            context: 检索到的相关上下文（用于验证真实性）

        Returns:
            JudgeResult 评测结果
        """
        user_prompt = f"""## 面试问题
{question}

## 候选人背景
{profile_summary or '未提供'}

## 相关经验上下文
{self._format_context(context or [])}

## 候选人回答
{answer}

请评分并返回 JSON。"""

        messages = [
            Message(role="system", content=self.SCORING_RUBRIC),
            Message(role="user", content=user_prompt),
        ]

        try:
            raw = await self.client.chat_sync(messages, temperature=0.2)
            result = self._parse_result(raw)
            result.raw_response = raw
            return result
        except Exception as e:
            return JudgeResult(
                scores={"error": 0},
                total=0,
                strengths=[],
                weaknesses=[f"评测失败: {str(e)}"],
            )

    async def evaluate_batch(
        self, questions: List[str], answers: List[str],
        profile_summary: str = ""
    ) -> List[JudgeResult]:
        """批量评测多个回答"""
        results = []
        for q, a in zip(questions, answers):
            result = await self.evaluate(q, a, profile_summary)
            results.append(result)
        return results

    async def compare_answers(
        self, question: str, answer_a: str, answer_b: str,
        label_a: str = "A", label_b: str = "B"
    ) -> Dict[str, Any]:
        """
        对比两个回答（用于 Prompt A/B 测试）

        Returns: {"winner": "A/B/tie", "comparison": "...", "score_diff": {...}}
        """
        prompt = f"""请对比以下两个面试回答，判断哪个更好。

## 面试问题
{question}

## 回答 {label_a}
{answer_a}

## 回答 {label_b}
{answer_b}

请从以下维度对比并返回 JSON：
{{
    "winner": "{label_a}" 或 "{label_b}" 或 "tie",
    "comparison": "详细的对比分析",
    "{label_a}_better": ["{label_a}更好的方面"],
    "{label_b}_better": ["{label_b}更好的方面"]
}}"""

        messages = [
            Message(role="system", content="你是面试回答质量评审专家。"),
            Message(role="user", content=prompt),
        ]

        raw = await self.client.chat_sync(messages, temperature=0.3)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"winner": "tie", "comparison": raw, "error": "JSON parse failed"}

    def _format_context(self, context: List[Dict]) -> str:
        """格式化上下文"""
        if not context:
            return "无"
        lines = []
        for i, ctx in enumerate(context[:5]):
            lines.append(f"{i+1}. [{ctx.get('collection', '')}] {ctx.get('content', '')[:200]}")
        return "\n".join(lines)

    def _parse_result(self, raw: str) -> JudgeResult:
        """解析 LLM 评测输出"""
        import re

        # 尝试直接解析
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    data = json.loads(match.group(0)) if match else {}
            else:
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                data = json.loads(match.group(0)) if match else {}

        scores = data.get("scores", {})
        total = data.get("total", sum(scores.values()) if scores else 0)

        return JudgeResult(
            scores=scores,
            total=float(total),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            needs_revision=data.get("needs_revision", False),
            feedback=data.get("feedback", ""),
        )


# 便捷函数
async def judge_answer(
    question: str, answer: str, profile: str = "", context: List[Dict] = None
) -> JudgeResult:
    """评测单个回答的便捷函数"""
    judge = LLMJudge()
    return await judge.evaluate(question, answer, profile, context)
