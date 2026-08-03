"""项目-JD 智能匹配引擎 — SPEC 需求2（P1）

功能：
1. JD 需求自动提取（技术栈 / 软技能 / 经验年限 / 职责）—— 纯规则化，无 LLM 依赖
2. 项目-JD 三维度匹配（技术交集 / 经验年限 / 复杂度）—— 从 ChromaDB 项目库读取真实项目打分排序
3. 针对性生成（STAR 面试回答 + 针对性简历项目描述）—— LLM 仅基于项目库真实数据润色，不虚构

LLM 使用边界：LLM 只做基于真实项目字段的针对性润色/组织，禁止编造项目或成果。
"""
import asyncio
import re
from typing import Dict, Any, List, Optional, Set

from src.rag.knowledge_graph import SkillGraph
from src.core.llm_client import get_client, Message


# ===== 1. JD 需求自动提取（纯规则化） =====

class JDRequirementExtractor:
    """从 JD 文本中提取需求：技术栈 / 软技能 / 经验年限 / 职责"""

    # 软技能词表（用于 JD 软技能要求提取）
    SOFT_SKILLS = [
        "沟通", "协作", "团队", "自驱", "责任心", "抗压", "学习能力", "逻辑思维",
        "解决问题", "主动性", "执行力", "细心", "韧性", "上进心", "抗压能力",
        "团队协作", "跨部门", "快速学习", "英语阅读", "文档写作",
    ]

    # 行为动词（用于职责提取）
    ACTION_VERBS = ["负责", "参与", "搭建", "设计", "实现", "优化", "开发", "主导", "编写", "维护", "构建"]

    def __init__(self):
        self.skill_graph = SkillGraph()

    def extract(self, jd_text: str) -> Dict[str, Any]:
        """提取 JD 需求。返回:
        {tech_stack: [...], soft_skills: [...], experience_years: Optional[int],
         keywords: [...], responsibilities: [...]}
        """
        return {
            "tech_stack": self._extract_tech(jd_text),
            "soft_skills": self._extract_soft_skills(jd_text),
            "experience_years": self._extract_years(jd_text),
            "keywords": self._extract_keywords(jd_text),
            "responsibilities": self._extract_responsibilities(jd_text),
        }

    def _extract_tech(self, jd_text: str) -> List[str]:
        """从 JD 提取技术栈：用 SkillGraph 的 CATEGORY_MAP 技能词做大小写不敏感匹配"""
        jd_lower = jd_text.lower()
        found: List[str] = []
        for category, skills in SkillGraph.CATEGORY_MAP.items():
            for skill in skills:
                # 词边界匹配，避免 "py" 误命中 "python" 等
                pattern = r'(?<![a-z0-9])' + re.escape(skill.lower()) + r'(?![a-z0-9])'
                if re.search(pattern, jd_lower):
                    found.append(skill)
        # 去重保序
        return list(dict.fromkeys(found))

    def _extract_soft_skills(self, jd_text: str) -> List[str]:
        """提取软技能要求"""
        return [s for s in self.SOFT_SKILLS if s in jd_text]

    def _extract_years(self, jd_text: str) -> Optional[int]:
        """提取经验年限（如"3年经验"）"""
        matches = re.findall(r'(\d{1,2})\s*[年+]', jd_text)
        if matches:
            years = [int(m) for m in matches]
            # 取最大的合理值（通常"3-5年"取5，或"3年以上"取3）
            return max(years) if years else None
        return None

    def _extract_keywords(self, jd_text: str) -> List[str]:
        """提取高频技术关键词（含大模型/向量库等归类词）"""
        keywords: List[str] = []
        # 归类词直接识别
        category_terms = ["大模型", "向量数据库", "RAG", "NLP", "深度学习", "机器学习",
                          "后端", "前端", "全栈", "算法", "分布式", "高并发", "微服务"]
        for term in category_terms:
            if term in jd_text:
                keywords.append(term)
        return keywords

    def _extract_responsibilities(self, jd_text: str) -> List[str]:
        """提取职责（以行为动词开头的短句）"""
        responsibilities: List[str] = []
        for line in re.split(r'[\n。；;]', jd_text):
            line = line.strip()
            if not line:
                continue
            if any(line.startswith(v) for v in self.ACTION_VERBS):
                responsibilities.append(line[:80])
        return responsibilities[:10]


# ===== 2. 项目-JD 三维度匹配 =====

class ProjectJDMatcher:
    """对项目库中的每个项目计算与 JD 的匹配度（三维度 + 综合分）"""

    def __init__(self):
        self.skill_graph = SkillGraph()

    def match_all(self, projects: List[Dict[str, Any]], jd_req: Dict[str, Any]) -> List[Dict[str, Any]]:
        """对每个项目计算三维度得分并排序。返回 List[Dict]，含:
        {name, role, tech_stack, time_period, key_result, match_score, tech_overlap,
         years_match, complexity_score, matched_tech, dimensions}
        """
        jd_tech = set(t.lower() for t in jd_req.get("tech_stack", []))
        jd_years = jd_req.get("experience_years")

        results = []
        for proj in projects:
            tech_stack = proj.get("tech_stack", []) or []
            if isinstance(tech_stack, str):
                tech_stack = [tech_stack]

            tech_overlap = self._tech_overlap(tech_stack, jd_tech)
            years_match = self._years_match(proj.get("time_period", ""), jd_years)
            complexity = self._complexity_score(proj, tech_stack)

            # 命中的技术交集（原始大小写，供展示）
            matched_tech = self._matched_tech(tech_stack, jd_tech)

            match_score = round(100 * (0.5 * tech_overlap + 0.25 * years_match + 0.25 * complexity), 1)

            results.append({
                "name": proj.get("name", ""),
                "role": proj.get("role", ""),
                "tech_stack": tech_stack,
                "time_period": proj.get("time_period", ""),
                "key_result": proj.get("key_result", ""),
                "match_score": match_score,
                "tech_overlap": round(tech_overlap, 2),
                "years_match": round(years_match, 2),
                "complexity_score": round(complexity, 2),
                "matched_tech": matched_tech,
            })

        # 按匹配分降序
        results.sort(key=lambda x: x["match_score"], reverse=True)
        return results

    def _tech_overlap(self, proj_tech: List[str], jd_tech: Set[str]) -> float:
        """技术交集：用 SkillGraph 归类做语义匹配（JD 写"大模型"，项目含 LangGraph 也算命中）"""
        if not jd_tech:
            # JD 无明确技术栈 → 中性偏高分
            return 0.7
        proj_lower = {t.lower() for t in proj_tech}
        hit = set()

        for jd_t in jd_tech:
            # 直接命中
            if jd_t in proj_lower:
                hit.add(jd_t)
                continue
            # 语义命中：JD 技术词的类别，项目技术词是否有同类别
            jd_cats = set(self.skill_graph.get_categories(jd_t))
            for p_t in proj_lower:
                p_cats = set(self.skill_graph.get_categories(p_t))
                if jd_cats and jd_cats & p_cats:
                    hit.add(jd_t)
                    break

        # 命中率 = 命中 JD 技术数 / JD 技术总数
        return min(1.0, len(hit) / len(jd_tech))

    def _matched_tech(self, proj_tech: List[str], jd_tech: Set[str]) -> List[str]:
        """返回项目中与 JD 命中的技术（用于展示）"""
        if not jd_tech:
            return proj_tech[:5]
        proj_lower = {t.lower(): t for t in proj_tech}
        matched: List[str] = []
        for jd_t in jd_tech:
            if jd_t in proj_lower:
                matched.append(proj_lower[jd_t])
            else:
                jd_cats = set(self.skill_graph.get_categories(jd_t))
                for p_t in proj_tech:
                    if set(self.skill_graph.get_categories(p_t)) & jd_cats:
                        matched.append(p_t)
                        break
        return list(dict.fromkeys(matched))[:8]

    def _years_match(self, time_period: str, jd_years: Optional[int]) -> float:
        """经验年限匹配：从项目时间段估算年限，与 JD 要求比较"""
        if jd_years is None:
            return 0.7  # JD 未要求年限 → 中性分
        if not time_period:
            return 0.5  # 无时间段 → 中性分

        # 估算项目年限（"2026.05 - 至今" → 至今算 1.5 年封顶）
        proj_years = self._estimate_years(time_period)
        if proj_years is None:
            return 0.6

        if proj_years >= jd_years:
            return 1.0
        return max(0.0, proj_years / max(jd_years, 1))

    @staticmethod
    def _estimate_years(time_period: str) -> Optional[float]:
        """从时间段字符串估算年限（年）。示例: "2026.05 - 至今" → ~0.3年（封顶1.5）；"2025.01 - 2026.03" → ~1.2年"""
        def _to_months(year: int, month: Optional[int]) -> int:
            return year * 12 + (month if month else 6)

        # "至今"场景：项目仍在进行，按起始至今估算（对当年启动的项目给 0.5 年保底）
        match_now = re.search(
            r'(\d{4})[\s./年]*(\d{1,2})?\s*[-–—至到]\s*(至今|现在|present|now)',
            time_period, re.IGNORECASE
        )
        if match_now:
            start_year = int(match_now.group(1))
            start_month = int(match_now.group(2)) if match_now.group(2) else None
            # 当前参考时间（固定用项目当前年份，避免依赖系统时间漂移）
            now_months = _to_months(2026, 8)
            proj_months = now_months - _to_months(start_year, start_month)
            # 当年启动的进行中项目给至少 0.5 年保底（避免出现近乎 0 的匹配分）
            return max(0.5, min(1.5, proj_months / 12.0))

        # 完整时间段："YYYY[.M] - YYYY[.M]"
        match = re.search(
            r'(\d{4})[\s./年]*(\d{1,2})?\s*[-–—至到]\s*(\d{4})[\s./年]*(\d{1,2})?',
            time_period
        )
        if match:
            start_months = _to_months(int(match.group(1)), int(match.group(2)) if match.group(2) else None)
            end_months = _to_months(int(match.group(3)), int(match.group(4)) if match.group(4) else None)
            return max(0.1, (end_months - start_months) / 12.0)

        return None

    def _complexity_score(self, proj: Dict[str, Any], tech_stack: List[str]) -> float:
        """复杂度：量化成果 + 技术栈数量 + 角色权重"""
        score = 0.3  # 基础分
        key_result = proj.get("key_result", "") or ""

        # 量化指标（数字/百分比）
        if re.search(r'\d+%|\d+(?:\.\d+)?(?:万|倍|个|次|ms|s)', key_result):
            score += 0.3
        # 技术栈数量
        if len(tech_stack) >= 4:
            score += 0.2
        elif len(tech_stack) >= 2:
            score += 0.1
        # 角色权重
        role = proj.get("role", "") or ""
        if any(k in role for k in ["负责人", "核心", "组长", "Owner", "主导"]):
            score += 0.2

        return min(1.0, score)


# ===== 3. 针对性生成（LLM，基于真实项目数据） =====

class TargetedGenerator:
    """基于匹配到的真实项目生成针对性 STAR 回答 / 简历项目描述"""

    def __init__(self):
        self.client = get_client()

    async def generate_answer(self, jd_req: Dict[str, Any], project: Dict[str, Any]) -> str:
        """生成针对性 STAR 面试回答（针对 Top 匹配项目）"""
        if not project or not project.get("name"):
            return ""

        project_text = self._format_project(project)
        jd_tech = ", ".join(jd_req.get("tech_stack", [])[:10]) or "未指定"
        jd_soft = ", ".join(jd_req.get("soft_skills", [])[:5]) or "未指定"

        system_prompt = """你是资深面试官。请基于候选人简历中的【真实项目素材】，用 STAR 模型（Situation→Task→Action→Result）生成一段针对性面试回答。

严格要求：
1. 只能使用下面提供的项目素材中的信息，绝不编造任何项目、技术或成果
2. 回答要点需向 JD 的技术要求（特别是命中的技术）靠拢
3. 用第一人称"我"，语气自信、具体、有量化数据
4. 输出纯文本回答，约 200-300 字，不要 JSON，不要标题"""
        user_prompt = f"""## 目标 JD 技术要求
{jd_tech}

## 目标 JD 软技能要求
{jd_soft}

## 我的真实项目素材
{project_text}

请基于以上真实素材生成针对性 STAR 面试回答。"""

        return await self._safe_generate(system_prompt, user_prompt)

    async def generate_resume_desc(self, jd_req: Dict[str, Any], project: Dict[str, Any]) -> str:
        """生成针对性简历项目描述（向 JD 需求靠拢的润色，不虚构）"""
        if not project or not project.get("name"):
            return ""

        project_text = self._format_project(project)
        jd_tech = ", ".join(jd_req.get("tech_stack", [])[:10]) or "未指定"

        system_prompt = """你是简历优化顾问。请基于候选人简历中的【真实项目素材】，将该项目描述改写为更贴合目标 JD 的版本。

严格要求：
1. 只能使用素材中已有的真实信息（项目名、角色、技术栈、成果、时间），不添加任何新内容
2. 突出与 JD 技术栈重合的技术，弱化无关细节
3. 格式：项目名一行 + 角色/时间一行 + 3-4 行要点（以行为动词开头）
4. 输出纯文本，不要 JSON"""
        user_prompt = f"""## 目标 JD 技术栈
{jd_tech}

## 我的真实项目素材
{project_text}

请改写为针对性简历项目描述。"""

        return await self._safe_generate(system_prompt, user_prompt)

    async def generate_resume_content(
        self, jd_req: Dict[str, Any], project: Dict[str, Any], user_skills: List[str],
        raw_skill_text: str = "",
    ) -> Dict[str, Any]:
        """生成针对性完整简历内容（含技术栈增强）。

        返回 {resume_content, added_skills, original_skills}
        - resume_content: 面向目标岗位的简历文本（技能+项目描述增强，保留原有基础）
        - added_skills: 新增的技术栈（JD 要求但简历未覆盖，保留原有技能）
        - raw_skill_text: 简历原始技能段落（作为输出格式模板，如"熟练掌握.../深入理解..."）
        """
        if not project or not project.get("name"):
            return {"resume_content": "", "added_skills": [], "original_skills": user_skills}

        project_text = self._format_project(project)
        jd_tech = ", ".join(jd_req.get("tech_stack", [])[:12]) or "未指定"
        skills_text = "、".join(dict.fromkeys(user_skills)) or "（简历未记录技能）"

        system_prompt = """你是资深简历优化顾问。请基于候选人真实简历，生成一份**更匹配目标 JD 的简历内容**。

## 核心要求
1. **技术栈增强（最重要）**：在候选人原有技能基础上，**补充目标 JD 要求但简历缺失的技能**，生成增强后的技能清单。
2. **输出格式必须严格遵循候选人简历原始技能段落的写法**——每行以"熟练掌握 / 深入理解 / 熟悉 / 熟练使用"等动词开头，写成一个完整的技能陈述句（技能 + 具体能力描述），不要逐项罗列孤立的技能名。
3. **原有技能段落一个都不删**，完整保留；新增技能以相同句式追加在对应位置（如补充"熟悉 LangGraph、ChromaDB 向量检索"这类 JD 要求项），并在新增行末尾标注「（建议补充）」。
4. **项目描述增强**：将 Top 匹配项目描述改写得更贴合 JD，突出与 JD 重合的技术，弱化无关细节。
5. **真实性约束**：项目描述只能使用简历中真实存在的内容，不编造简历没有的量化成果；新增技能是"建议补充项"，不属于简历事实陈述。
6. 格式清晰，输出纯文本。"""
        user_prompt = f"""## 目标 JD 技术栈要求
{jd_tech}

## 候选人简历原始技能段落（必须严格沿用此格式输出）
{raw_skill_text if raw_skill_text else skills_text}

## 我的真实项目素材（Top 匹配项目）
{project_text}

请生成增强后的简历内容。输出格式：
【增强后技能】
（严格沿用原始技能段落格式，原有每行保留 + 新增行以相同句式追加并标注「（建议补充）」）
【项目描述增强】
（面向 JD 优化后的项目描述，3-4 行要点）"""

        # 解析新增技能：JD 要求且不在原技能中（规则化，不依赖 LLM）
        original_lower = {s.lower() for s in user_skills}
        added_skills = [t for t in jd_req.get("tech_stack", []) if t.lower() not in original_lower]

        # 生成并重试：LLM 偶发返回空/过短内容，重试最多 4 次（格式模板 prompt 响应方差大）
        raw = ""
        for attempt in range(4):
            raw = await self._safe_generate(system_prompt, user_prompt, max_tokens=1500)
            if raw and len(raw) >= 100:
                break
            await asyncio.sleep(1)
        if not raw or len(raw) < 50:
            # LLM 失败时仍返回规则化的新增技能建议
            return {"resume_content": "", "added_skills": added_skills, "original_skills": user_skills}

        return {
            "resume_content": raw,
            "added_skills": added_skills,
            "original_skills": user_skills,
        }

    def _format_project(self, project: Dict[str, Any]) -> str:
        """格式化项目为素材文本"""
        tech = ", ".join(project.get("tech_stack", []) or [])
        lines = [
            f"项目名: {project.get('name', '')}",
            f"角色: {project.get('role', '')}",
            f"技术栈: {tech}",
            f"时间段: {project.get('time_period', '')}",
            f"关键成果: {project.get('key_result', '')}",
        ]
        desc = project.get("description", "")
        if desc:
            lines.append(f"描述: {desc[:500]}")
        return "\n".join(lines)

    async def _safe_generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024, timeout: int = None) -> str:
        """LLM 调用 + 错误隔离（失败返回空串）。
        注意：必须使用全局单例 client（get_client），新建 DeepSeekClient 实例会导致响应异常变短。"""
        try:
            from src.core.llm_client import get_client
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]
            result = await self.client.chat_sync(messages, temperature=0.6, max_tokens=max_tokens)
            return result.strip()
        except Exception as e:
            import traceback
            print(f"[WARN] _safe_generate 失败: {type(e).__name__}: {str(e)[:150]}")
            return ""


# ===== 4. 顶层编排 =====

class ProjectJDMatchService:
    """项目-JD 匹配服务：提取 JD 需求 → 读项目库 → 匹配排序 → 针对性生成"""

    def __init__(self):
        self.extractor = JDRequirementExtractor()
        self.matcher = ProjectJDMatcher()
        self.generator = TargetedGenerator()

    async def analyze(
        self, jd_text: str, target_position: str = "", vs=None
    ) -> Dict[str, Any]:
        """组合分析。vs 为 vector_store 实例（可为 None，此时尝试延迟加载）。
        返回 {jd_requirements, projects, top_project, targeted_answer,
              targeted_resume_desc, matched_skills, missing_skills, message}
        """
        # 1. JD 需求提取（规则化）
        jd_req = self.extractor.extract(jd_text)

        # 2. 读取项目库
        projects = self._load_projects(vs)
        if not projects:
            return {
                "jd_requirements": jd_req,
                "projects": [],
                "top_project": None,
                "targeted_answer": "",
                "targeted_resume_desc": "",
                "matched_skills": jd_req.get("tech_stack", []),
                "missing_skills": [],
                "message": "暂无项目数据，请先上传简历",
            }

        # 3. 匹配排序
        matched = self.matcher.match_all(projects, jd_req)

        # 4. 针对性生成（对 Top-1 项目，串行 2 次 LLM 调用，避免并发限流/超时）
        top_project = matched[0] if matched else None
        targeted_answer = ""
        resume_content = ""
        added_skills = []
        if top_project:
            # 补充原始描述/成果字段供生成使用
            top_full = self._find_full(projects, top_project.get("name"))
            target = top_full or top_project
            user_skills = self._load_user_skills()
            raw_skill_text = self._load_raw_skill_text()
            # 串行生成：STAR 回答 → 完整简历内容（含技术栈增强 + 项目描述增强）
            targeted_answer = await self.generator.generate_answer(jd_req, target)
            content_res = await self.generator.generate_resume_content(
                jd_req, target, user_skills, raw_skill_text=raw_skill_text
            )
            resume_content = content_res.get("resume_content", "") if content_res else ""
            added_skills = content_res.get("added_skills", []) if content_res else []

        # 技能差距（JD 技术栈中项目库未覆盖的）
        covered = set()
        for p in matched:
            covered.update(p.get("matched_tech", []))
        jd_tech_lower = {t.lower() for t in jd_req.get("tech_stack", [])}
        covered_lower = {c.lower() for c in covered}
        missing_skills = [t for t in jd_req.get("tech_stack", []) if t.lower() not in covered_lower]

        return {
            "jd_requirements": jd_req,
            "projects": matched,
            "top_project": top_project,
            "targeted_answer": targeted_answer,
            "targeted_resume_desc": resume_content,  # 兼容旧字段：简历增强内容
            "resume_content": resume_content,
            "added_skills": added_skills,
            "matched_skills": jd_req.get("tech_stack", []),
            "missing_skills": missing_skills,
            "message": "",
        }

    def _load_user_skills(self) -> List[str]:
        """从结构化档案读取用户技能列表"""
        try:
            from src.features.profile_store import ProfileStore
            profile = ProfileStore.load()
            skills = profile.get("skills", [])
            names = []
            for s in skills:
                if isinstance(s, dict):
                    name = s.get("name", "")
                else:
                    name = str(s)
                if name and name not in names:
                    names.append(name)
            return names[:50]
        except Exception:
            return []

    def _load_raw_skill_text(self) -> str:
        """从原始简历文本提取技能段落（作为输出格式模板）。

        技能段落通常每行以"熟练掌握/深入理解/熟悉/熟练使用"等开头，
        保留该原始格式供 LLM 生成增强版技能清单时沿用。
        """
        try:
            import glob
            from src.rag.parser import ResumeParser
            # 找最近上传的简历
            files = sorted(glob.glob("data/resumes/*"), key=lambda f: __import__("os").path.getmtime(f), reverse=True)
            for fp in files:
                if not fp.lower().endswith((".pdf", ".docx", ".md", ".txt")):
                    continue
                try:
                    p = ResumeParser()
                    parsed = p.parse(fp)
                    skill_text = parsed.sections.get("skills", "").strip()
                    if skill_text and len(skill_text) > 30:
                        return skill_text[:1500]
                except Exception:
                    continue
            return ""
        except Exception:
            return ""

    def _load_projects(self, vs) -> List[Dict[str, Any]]:
        """读取项目库。优先从结构化档案 (data/profile.json) 读取（可靠），
        档案为空时降级从 ChromaDB projects 集合尽力聚合。vs 可传 None 以延迟加载。"""
        # 首选：结构化项目库
        try:
            from src.features.profile_store import ProfileStore
            profile_projects = ProfileStore.get_projects()
            if profile_projects:
                return profile_projects
        except Exception:
            pass

        # 降级：ChromaDB 碎 chunk 聚合（尽力而为）
        try:
            if vs is None:
                from src.rag.vector_store import get_vector_store
                vs = get_vector_store()
            info = vs.get_collection_info()
            if not info.get("projects", 0):
                return []
            results = vs.search("", "projects", top_k=100)
        except Exception:
            return []

        projects: List[Dict[str, Any]] = []
        seen = set()
        for r in results:
            metadata = r.get("metadata", {}) or {}
            name = metadata.get("name", "") or r.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            # 解析 content 字符串（parser 只把 name/role 放 metadata，技术栈/成果在 content 里）
            content = r.get("content", "") or ""
            parsed = self._parse_project_content(content)
            projects.append({
                "name": name,
                "role": metadata.get("role", "") or parsed["role"],
                "tech_stack": parsed["tech_stack"],
                "time_period": parsed["time_period"],
                "key_result": parsed["key_result"],
                "description": content,
            })
        return projects

    @staticmethod
    def _parse_project_content(content: str) -> Dict[str, Any]:
        """从 ChromaDB 项目 content 字符串解析结构化字段。
        格式: "项目: X\n角色: Y\n技术栈: A, B\n关键成果: Z"
        """
        result = {"role": "", "tech_stack": [], "time_period": "", "key_result": ""}
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("角色:") or line.startswith("角色："):
                result["role"] = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            elif line.startswith("技术栈:") or line.startswith("技术栈："):
                raw = line.split(":", 1)[-1].split("：", 1)[-1].strip()
                result["tech_stack"] = [t.strip() for t in re.split(r'[,，、]', raw) if t.strip()]
            elif line.startswith("关键成果:") or line.startswith("关键成果："):
                result["key_result"] = line.split(":", 1)[-1].split("：", 1)[-1].strip()
        return result

    def _find_full(self, projects: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
        """从原始项目列表找回含 description 的完整记录"""
        for p in projects:
            if p.get("name") == name:
                return p
        return None
