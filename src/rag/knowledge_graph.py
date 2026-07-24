"""技能知识图谱 - 技能↔项目↔成果 结构化关系"""
from typing import List, Dict, Any, Optional, Set, Tuple


class SkillGraph:
    """
    技能知识图谱

    解决"归类词→具体词"的语义鸿沟：
    - 用户问："你用过哪些向量数据库？"
    - 简历写："FAISS" "ChromaDB"
    - 图谱推理：向量数据库 → [FAISS, ChromaDB] → [PaperPilot项目, ResuMatch项目] → [延迟降低80%, 引用准确率100%]

    结构：
    - 类别节点 (Category): 技术大类
    - 技能节点 (Skill): 具体技术/工具
    - 项目节点 (Project): 项目经验
    - 成果节点 (Achievement): 量化成果
    - 边 (Edge): includes, used_in, achieved, related_to
    """

    # 预定义的技术分类体系
    CATEGORY_MAP: Dict[str, List[str]] = {
        # 编程语言
        "编程语言": ["Python", "Java", "Go", "Rust", "C++", "C", "TypeScript", "JavaScript",
                   "SQL", "Shell", "Scala", "Kotlin", "Swift"],
        # 后端框架
        "后端框架": ["FastAPI", "Django", "Flask", "Spring", "Spring Boot", "Gin", "Express",
                   "NestJS", "Actix", "Rocket"],
        # 前端框架
        "前端框架": ["React", "Vue", "Vue.js", "Angular", "Next.js", "Nuxt", "Svelte",
                   "Streamlit", "Gradio"],
        # 数据库
        "数据库": ["MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite", "Oracle",
                 "ClickHouse", "TiDB", "OceanBase"],
        # 向量数据库
        "向量数据库": ["FAISS", "ChromaDB", "Milvus", "Pinecone", "Weaviate", "Qdrant",
                    "Elasticsearch", "Vespa"],
        # 消息队列
        "消息队列": ["Kafka", "RabbitMQ", "RocketMQ", "Pulsar", "Redis Streams", "NATS"],
        # 容器化
        "容器化": ["Docker", "Kubernetes", "K8s", "Podman", "Containerd", "Helm"],
        # CI/CD
        "CI/CD": ["Jenkins", "GitHub Actions", "GitLab CI", "ArgoCD", "Tekton", "Drone"],
        # LLM/大模型
        "大模型": ["GPT", "GPT-4", "Claude", "DeepSeek", "Qwen", "LLaMA", "ChatGLM",
                 "Mistral", "Gemini", "RAG", "LangChain", "LangGraph"],
        # NLP
        "NLP": ["BERT", "Transformer", "Word2Vec", "jieba", "spaCy", "HuggingFace",
               "Sentence-Transformers", "bge", "text2vec"],
        # 嵌入模型
        "嵌入模型": ["bge-small-zh", "bge-large-zh", "text2vec", "m3e", "all-MiniLM-L6-v2",
                   "OpenAI Embedding", "Cohere Embed"],
        # 工作流框架
        "工作流框架": ["LangGraph", "Airflow", "Prefect", "Dagster", "Temporal", "Cadence"],
        # 微调技术
        "微调技术": ["LoRA", "QLoRA", "P-Tuning", "Prefix Tuning", "Full Fine-tuning",
                   "SFT", "RLHF", "DPO"],
        # 监控
        "监控": ["Prometheus", "Grafana", "ELK", "Datadog", "OpenTelemetry", "Jaeger"],
        # 云平台
        "云平台": ["AWS", "阿里云", "腾讯云", "华为云", "GCP", "Azure"],
        # Agent 框架
        "Agent框架": ["ReAct", "AutoGPT", "MetaGPT", "CrewAI", "AutoGen", "AgentScope"],
    }

    def __init__(self):
        self._build_graph()

    def _build_graph(self) -> None:
        """构建内部索引"""
        # skill → [categories]
        self.skill_to_categories: Dict[str, List[str]] = {}
        for category, skills in self.CATEGORY_MAP.items():
            for skill in skills:
                skill_lower = skill.lower()
                if skill_lower not in self.skill_to_categories:
                    self.skill_to_categories[skill_lower] = []
                self.skill_to_categories[skill_lower].append(category)

        # category → skills
        self.category_to_skills: Dict[str, List[str]] = {}
        for category, skills in self.CATEGORY_MAP.items():
            self.category_to_skills[category.lower()] = skills

    def expand_query(self, query: str) -> List[str]:
        """
        查询扩展：将归类词展开为具体技能/工具

        示例：
        "向量数据库" → ["FAISS", "ChromaDB", "Milvus", "Pinecone", "Weaviate", "Qdrant", "Elasticsearch", "Vespa"]
        "大模型" → ["GPT", "Claude", "DeepSeek", "Qwen", "LLaMA", ...]
        """
        query_lower = query.lower()
        expansions = set()

        # 精确匹配类别
        for category, skills in self.category_to_skills.items():
            if category in query_lower or query_lower in category:
                expansions.update(skills)

        # 部分匹配（查询词包含在类别名中）
        if not expansions:
            for category, skills in self.category_to_skills.items():
                if any(word in category for word in query_lower.split()):
                    expansions.update(skills)

        return list(expansions)

    def get_categories(self, skill: str) -> List[str]:
        """获取技能所属的类别"""
        return self.skill_to_categories.get(skill.lower(), [])

    def find_related_skills(self, skill: str) -> List[str]:
        """查找与给定技能同类的其他技能"""
        categories = self.get_categories(skill)
        related = set()
        for cat in categories:
            related.update(self.category_to_skills.get(cat.lower(), []))
        related.discard(skill)
        return list(related)

    def get_skill_siblings(self, skill: str) -> Dict[str, List[str]]:
        """
        获取同类技能分组（用于"你还用过哪些XX？"类追问）

        返回: {category_name: [sibling_skills]}
        """
        categories = self.get_categories(skill)
        result = {}
        for cat in categories:
            siblings = self.category_to_skills.get(cat.lower(), [])
            result[cat] = [s for s in siblings if s.lower() != skill.lower()]
        return result

    def build_project_chain(
        self, parsed_resume: Any
    ) -> List[Dict[str, Any]]:
        """
        构建 "技能 → 项目 → 成果" 完整链路

        用于回答"请介绍一个你使用 XX 技术的项目"
        """
        chains = []

        projects = getattr(parsed_resume, 'projects', [])
        skills = getattr(parsed_resume, 'skills', [])
        achievements = getattr(parsed_resume, 'achievements', [])

        for proj in projects:
            proj_techs = proj.get("tech_stack", [])
            if isinstance(proj_techs, str):
                proj_techs = [proj_techs]

            # 为每个技术找到类别
            tech_with_categories = []
            for tech in proj_techs:
                categories = self.get_categories(tech)
                tech_with_categories.append({
                    "skill": tech,
                    "categories": categories,
                    "related": self.find_related_skills(tech),
                })

            # 找到关联的成果
            proj_name = proj.get("name", "")
            related_achievements = [
                a for a in achievements
                if proj_name.lower() in a.get("description", "").lower()
            ]

            chains.append({
                "project": proj,
                "technologies": tech_with_categories,
                "achievements": related_achievements,
            })

        return chains

    def detect_skill_gaps(self, target_role: str, user_skills: List[str]) -> Dict[str, Any]:
        """
        检测技能差距（用于 JD 匹配）

        Args:
            target_role: 目标职位（如 "后端开发工程师"）
            user_skills: 用户已有技能列表

        Returns: {missing_categories, recommended_skills, match_rate}
        """
        # 根据目标职位确定期望的技能类别
        role_requirements = {
            "后端": ["编程语言", "后端框架", "数据库", "消息队列", "容器化", "CI/CD", "监控", "云平台"],
            "前端": ["编程语言", "前端框架", "CI/CD", "监控"],
            "算法": ["编程语言", "大模型", "NLP", "微调技术", "嵌入模型"],
            "devops": ["编程语言", "容器化", "CI/CD", "监控", "云平台", "消息队列"],
            "数据": ["编程语言", "数据库", "消息队列", "监控"],
        }

        # 匹配角色
        matched_role = "后端"
        for role in role_requirements:
            if role in target_role:
                matched_role = role
                break

        required_categories = role_requirements.get(matched_role, role_requirements["后端"])

        # 找到用户技能的类别
        user_categories = set()
        user_skills_lower = [s.lower() for s in user_skills]
        for skill in user_skills_lower:
            user_categories.update(self.get_categories(skill))

        # 缺失类别
        missing = [cat for cat in required_categories if cat not in user_categories]

        # 推荐技能（缺失类别中的代表性技能）
        recommended = []
        for cat in missing:
            skills_in_cat = self.category_to_skills.get(cat.lower(), [])
            recommended.extend(skills_in_cat[:3])

        match_rate = (len(required_categories) - len(missing)) / len(required_categories)

        return {
            "target_role": target_role,
            "matched_role_template": matched_role,
            "required_categories": required_categories,
            "covered_categories": list(user_categories & set(required_categories)),
            "missing_categories": missing,
            "recommended_skills": recommended,
            "match_rate": round(match_rate, 2),
        }
