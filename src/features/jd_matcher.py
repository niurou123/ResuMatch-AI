"""JD-简历匹配度分析"""
import json
from typing import Dict, Any, List
from src.core.llm_client import get_client, Message
from src.rag.knowledge_graph import SkillGraph


class JDMatchAnalyzer:
    """JD-简历匹配度分析器"""

    def __init__(self):
        self.client = get_client()
        self.skill_graph = SkillGraph()

    async def analyze(
        self, jd_text: str, user_skills: List[str],
        user_projects: List[Dict] = None,
        target_position: str = "",
    ) -> Dict[str, Any]:
        """
        分析 JD 与简历的匹配度

        Returns:
            {
                "match_score": 0-100,
                "match_rate": 0.0-1.0,
                "matched_skills": [...],
                "missing_skills": [...],
                "recommended_skills": [...],
                "missing_categories": [...],
                "strength_analysis": "...",
                "gap_analysis": "...",
                "highlights": [...],
                "action_items": [...]
            }
        """
        # 1. Skill Graph 结构化分析
        graph_result = self.skill_graph.detect_skill_gaps(target_position, user_skills)

        # 2. LLM 深度分析
        llm_result = await self._llm_analysis(
            jd_text, user_skills, user_projects, target_position
        )

        # 3. 合并结果
        return {
            "match_score": llm_result.get("match_score", graph_result["match_rate"] * 100),
            "match_rate": graph_result["match_rate"],
            "matched_skills": llm_result.get("matched_skills", []),
            "missing_skills": llm_result.get("missing_skills", graph_result["recommended_skills"]),
            "recommended_skills": graph_result["recommended_skills"],
            "missing_categories": graph_result["missing_categories"],
            "strength_analysis": llm_result.get("strength_analysis", ""),
            "gap_analysis": llm_result.get("gap_analysis", ""),
            "highlights": llm_result.get("highlights", []),
            "action_items": llm_result.get("action_items", []),
        }

    async def _llm_analysis(
        self, jd_text: str, user_skills: List[str],
        user_projects: List[Dict] = None,
        target_position: str = "",
    ) -> Dict[str, Any]:
        """LLM 深度分析"""
        # 截断 JD 防止超出 token 限制
        jd_truncated = jd_text[:3000] if len(jd_text) > 3000 else jd_text

        projects_text = ""
        if user_projects:
            for p in user_projects[:5]:
                name = p.get("name", "")
                tech = p.get("tech_stack", [])
                tech_str = ", ".join(tech) if isinstance(tech, list) else str(tech)
                result = p.get("key_result", "")
                projects_text += f"- {name}: {tech_str}"
                if result:
                    projects_text += f" (成果: {result})"
                projects_text += "\n"

        system_prompt = """你是资深技术招聘专家。请分析JD与候选人简历的匹配度。

返回 JSON：
{
    "match_score": 0-100 (整数),
    "matched_skills": ["JD要求且候选人具备的技能"],
    "missing_skills": ["JD要求但候选人缺乏的技能"],
    "strength_analysis": "候选人的优势分析（100字）",
    "gap_analysis": "需要补强的方向（100字）",
    "highlights": ["面试中应该强调的3个亮点"],
    "action_items": ["面试前应该准备的3件事"]
}"""

        user_prompt = f"""## 职位描述 (JD)
{jd_truncated}

## 岗位: {target_position or '未指定'}

## 候选人技能
{', '.join(user_skills[:30])}

## 候选人项目经验
{projects_text or '未提供'}

请分析匹配度。"""

        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]
            raw = await self.client.chat_sync(messages, temperature=0.3)
            # 提取 JSON
            import re
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass

        return {}

    def quick_match(self, jd_text: str, user_skills: List[str]) -> Dict[str, Any]:
        """
        快速匹配（规则化，无 LLM 调用）
        适用于需要即时反馈的场景
        """
        jd_lower = jd_text.lower()

        matched = []
        missing = []

        for skill in user_skills:
            if skill.lower() in jd_lower:
                matched.append(skill)
            else:
                missing.append(skill)

        # JD 中可能需要的技能（简单关键词提取）
        common_tech_keywords = [
            "Python", "Java", "Go", "JavaScript", "TypeScript", "C++", "Rust",
            "React", "Vue", "Angular", "Next.js",
            "FastAPI", "Django", "Spring", "Express",
            "MySQL", "PostgreSQL", "MongoDB", "Redis",
            "Docker", "Kubernetes", "AWS", "Azure",
            "TensorFlow", "PyTorch", "LangChain", "LangGraph",
            "Kafka", "RabbitMQ", "gRPC", "GraphQL",
        ]

        jd_required = [kw for kw in common_tech_keywords if kw.lower() in jd_lower]
        missing_from_jd = [kw for kw in jd_required if kw not in user_skills]

        match_rate = len(matched) / max(len(user_skills), 1)

        return {
            "match_score": round(match_rate * 100),
            "match_rate": round(match_rate, 2),
            "matched_skills": matched[:10],
            "missing_skills": missing_from_jd[:10],
            "total_user_skills": len(user_skills),
            "jd_required_count": len(jd_required),
        }
