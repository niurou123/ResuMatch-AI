"""
字段标准化映射器 — LLM仅在此处介入

P0 原则：
- ✅ LLM 可用于：技能名标准化（"react" → "React.js"）、技术栈归类
- ❌ LLM 不可用于：内容概括、总结、改写、生成
- 标准化是可选步骤，解析器独立运行不依赖 LLM
- 每个标准化结果保留原始值，用户可对比
"""
import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from src.core.llm_client import get_client, Message


@dataclass
class NormalizedField:
    """标准化后的字段"""
    original: str          # 原始值（来自解析器）
    normalized: str        # 标准化后的值
    field_type: str        # skill / project_name / tech / role
    confidence: float      # 标准化置信度
    alternatives: List[str] = field(default_factory=list)  # 其他可能的标准化形式


class SkillNormalizer:
    """
    技能名标准化器

    使用 LLM 将自由文本中的技能名映射到标准形式。
    仅做名称标准化，不改变提取结果。

    示例：
      "react"     → "React.js"
      "nextjs"    → "Next.js"
      "k8s"       → "Kubernetes"
      "golang"    → "Go"
      "vue3"      → "Vue.js 3.x"
      "机器学习"   → "Machine Learning"
    """

    NORMALIZE_PROMPT = """你是一个技术名词标准化工具。你的唯一任务是将非标准的技术名词映射到标准形式。

## 严格规则
1. 只做名称标准化，不要做任何概括、总结或解释
2. 如果已经标准，直接返回原名
3. 如果无法确定标准形式，返回原名
4. 不要改变技术名词的含义和范围

## 示例
输入: ["react", "nextjs", "k8s", "golang", "python", "机器学习"]
输出: {"react": "React.js", "nextjs": "Next.js", "k8s": "Kubernetes", "golang": "Go", "python": "Python", "机器学习": "Machine Learning"}

输入: ["Java", "Spring Boot", "MySQL"]
输出: {"Java": "Java", "Spring Boot": "Spring Boot", "MySQL": "MySQL"}

严格返回 JSON 对象（不要其他文字）：{"原始值": "标准化值", ...}"""

    def __init__(self):
        self._builtin_map = {
            # 编程语言
            "js": "JavaScript", "ts": "TypeScript", "py": "Python",
            "cpp": "C++", "c++": "C++", "c#": "C#",
            "golang": "Go", "go": "Go",

            # 框架
            "react": "React.js", "reactjs": "React.js",
            "vue": "Vue.js", "vuejs": "Vue.js", "vue3": "Vue.js 3.x",
            "nextjs": "Next.js", "next.js": "Next.js",
            "nestjs": "NestJS",

            # 基础设施
            "k8s": "Kubernetes", "k3s": "K3s",
            "ec2": "Amazon EC2", "s3": "Amazon S3",
            "rds": "Amazon RDS",

            # AI/ML
            "dl": "Deep Learning",
            "ml": "Machine Learning",
            "nlp": "Natural Language Processing",
            "cv": "Computer Vision",
            "llm": "Large Language Model",

            # 数据库
            "pg": "PostgreSQL", "mongo": "MongoDB",
            "es": "Elasticsearch", " chroma": "ChromaDB",
        }

    def normalize_builtin(self, name: str) -> str:
        """使用内置映射表快速标准化（零延迟）"""
        return self._builtin_map.get(name.lower().strip(), name)

    async def normalize_batch(self, names: List[str]) -> Dict[str, NormalizedField]:
        """使用 LLM 批量标准化技能名"""
        if not names:
            return {}

        # 先用内置映射
        results = {}
        unknown = []
        for name in names:
            builtin = self.normalize_builtin(name)
            if builtin != name:
                results[name] = NormalizedField(
                    original=name, normalized=builtin,
                    field_type="skill", confidence=0.95,
                )
            else:
                unknown.append(name)

        if not unknown:
            return results

        # 对未知名称使用 LLM 标准化
        try:
            client = get_client()
            messages = [
                Message(role="system", content=self.NORMALIZE_PROMPT),
                Message(role="user", content=json.dumps(unknown, ensure_ascii=False)),
            ]
            raw = await client.chat_sync(messages, temperature=0.1, max_tokens=500)

            # 解析 JSON
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                llm_result = json.loads(match.group(0))
                for name in unknown:
                    normalized = llm_result.get(name, name)
                    results[name] = NormalizedField(
                        original=name, normalized=normalized,
                        field_type="skill",
                        confidence=0.7 if normalized != name else 0.5,
                    )
        except Exception:
            # LLM 不可用时，所有未知名称保持原样
            for name in unknown:
                results[name] = NormalizedField(
                    original=name, normalized=name,
                    field_type="skill", confidence=0.3,
                )

        return results

    async def normalize_single(self, name: str) -> NormalizedField:
        """标准化单个技能名"""
        results = await self.normalize_batch([name])
        return results.get(name, NormalizedField(
            original=name, normalized=name,
            field_type="skill", confidence=0.3,
        ))


class ProjectNameNormalizer:
    """
    项目名标准化器

    将自由文本中的项目名规范化。
    不做内容概括，仅规范化格式。

    示例：
      "paperpilot"          → "PaperPilot"
      "resumatch ai"        → "ResuMatch AI"
      "基于LangGraph的RAG系统" → "基于LangGraph的RAG系统" (中文保持原样)
    """

    NORMALIZE_PROMPT = """你是一个项目名称标准化工具。你只做名称格式规范化。

## 规则
1. 英文项目名转为 Title Case（每个单词首字母大写）
2. 中文项目名保持原样
3. 不要概括或改写项目名
4. 不要添加或删除任何描述信息

严格返回 JSON 对象：{"原始名": "规范化名", ...}"""

    async def normalize_batch(self, names: List[str]) -> Dict[str, NormalizedField]:
        """批量标准化项目名"""
        if not names:
            return {}

        results = {}
        # 对纯英文名，本地做 Title Case
        needs_llm = []
        for name in names:
            if re.match(r'^[a-zA-Z][a-zA-Z0-9\s_-]+$', name):
                # 简单英文名，本地处理
                normalized = name.strip().title().replace('_', ' ').replace('-', ' ')
                # 合并多余空格
                normalized = re.sub(r'\s+', ' ', normalized)
                results[name] = NormalizedField(
                    original=name, normalized=normalized,
                    field_type="project_name", confidence=0.9,
                )
            else:
                needs_llm.append(name)

        if not needs_llm:
            return results

        try:
            client = get_client()
            messages = [
                Message(role="system", content=self.NORMALIZE_PROMPT),
                Message(role="user", content=json.dumps(needs_llm, ensure_ascii=False)),
            ]
            raw = await client.chat_sync(messages, temperature=0.1, max_tokens=300)
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                llm_result = json.loads(match.group(0))
                for name in needs_llm:
                    normalized = llm_result.get(name, name)
                    results[name] = NormalizedField(
                        original=name, normalized=normalized,
                        field_type="project_name",
                        confidence=0.7 if normalized != name else 0.5,
                    )
        except Exception:
            for name in needs_llm:
                results[name] = NormalizedField(
                    original=name, normalized=name,
                    field_type="project_name", confidence=0.3,
                )

        return results


# ============ 便捷函数 ============

async def normalize_parsed_resume(parsed: Any) -> Dict[str, Any]:
    """
    对已解析的简历进行字段标准化（可选步骤）

    Args:
        parsed: ParsedResume 对象

    Returns:
        { "skills": {原始: NormalizedField}, "projects": {原始: NormalizedField} }
    """
    skill_normalizer = SkillNormalizer()
    project_normalizer = ProjectNameNormalizer()

    skill_names = [s.get("name", "") for s in parsed.skills if s.get("name")]
    project_names = [p.get("name", "") for p in parsed.projects if p.get("name")]

    # 并行标准化
    import asyncio
    skills_norm, projects_norm = await asyncio.gather(
        skill_normalizer.normalize_batch(skill_names),
        project_normalizer.normalize_batch(project_names),
    )

    return {
        "skills": skills_norm,
        "projects": projects_norm,
    }
