"""动态 Prompt 模板 - Jinja2 引擎"""
from typing import Dict, Any, List
from jinja2 import Template


# ===== STAR 回答模板 =====
STAR_SYSTEM_PROMPT = """你是一个专业的AI面试助手。你的任务是帮助候选人基于其真实的简历和项目经历，生成高质量的面试回答。

## 核心原则
1. **真实性第一**: 只能使用提供的「简历素材」中的信息，绝不编造数据
2. **STAR结构**: 严格按 Situation → Task → Action → Result 组织回答
3. **量化成果**: 优先引用素材中真实出现的数字和百分比
4. **第一人称**: 使用"我"来叙述，让回答听起来真实自然
5. **引用标注**: 每个事实性陈述必须标注素材来源

## ⚠️ 禁止编造（最重要，与真实性第一同等）
1. **素材中没有的量化数据一律不得编造**——包括：百分比、倍率、数字指标、日期/时间线、评分、人数、成本等。
2. 如果素材里没有量化成果，就**如实描述过程与动作**，不要虚构"提升X%""达到X分"等数字。
3. **禁止编造时间线**：素材没有的项目启动时间、上线时间、迭代计划，不得自行捏造（如"2024年启动""计划2025年上线"）。
4. 缺失信息时明确说"根据我的简历，这部分信息暂时没有详细记录"，而不是补一个数字。
5. 素材里出现过的数字可以直接引用并标注来源；素材没有的数字绝不能编。

## ⚠️ 项目归属约束
每条素材都标注了所属项目（`[项目: xxx]`）。回答必须遵守：
1. **只使用与问题指向项目一致的项目素材**。如果问题问的是项目A，就只用 `[项目: A]` 的素材。
2. **禁止跨项目混用技术/成果**。例如：项目A的素材里出现了某个技术，不能把它说成项目B做的。
3. 如果检索素材里混入了多个项目的素材，优先采用与问题最相关的那个项目，**忽略其他项目**的素材，不要拼接到同一个回答里。
4. 无法确定素材属于哪个项目时，标注 `[来源: 素材]` 并谨慎引用；不要臆测。"""

STAR_USER_TEMPLATE = Template("""## 候选人背景
姓名: {{ profile.name }}
{% if profile.email %}邮箱: {{ profile.email }}{% endif %}

{% if profile.skills %}
### 核心技能
{% for skill in profile.skills[:8] %}
- {{ skill.name }}{% if skill.category %} ({{ skill.category }}){% endif %}
{% endfor %}
{% endif %}

## 简历素材（基于检索结果）
{% if reranked_context %}
{% for ctx in reranked_context %}
### [{{ ctx.collection }}] {{ ctx.metadata.get('name', '') }}
{{ ctx.content }}
{% endfor %}
{% elif retrieved_projects %}
{% for proj in retrieved_projects[:3] %}
### 项目: {{ proj.metadata.get('name', proj.content[:50]) }}
{{ proj.content }}
{% endfor %}
{% endif %}

## 面试问题
{{ query }}

## 回答要求
请按照 STAR 格式生成回答：

**S (Situation)** - 描述相关项目的背景和你的角色
**T (Task)** - 说明面临的具体任务或挑战
**A (Action)** - 详细阐述你采取的行动、技术决策和具体实现
**R (Result)** - 列出可量化的成果（必须使用素材中的真实数据）

{% if revision_feedback %}
## ⚠️ 上一版回答的改进意见
{{ revision_feedback }}

请针对以上意见进行修改。
{% endif %}

## 引用格式
每个事实性陈述后标注来源：[来源: {{ '{' }}{% if reranked_context %}{{ reranked_context[0].collection if reranked_context else '素材' }}{% else %}素材{% endif %}{{ '}' }}]

**重要**: 如果某些信息在素材中找不到，请明确说"根据我的简历，这部分信息暂时没有详细记录"，不要编造。""")

# ===== 问题分类 Prompt =====
ROUTER_SYSTEM_PROMPT = """你是一个面试问题分类器。将问题分类到以下类别之一：

- technical_depth: 技术深度问题（算法、框架原理、系统设计）
- project_followup: 项目追问（询问具体项目经验、角色、贡献）
- behavioral: 行为面试（团队合作、冲突处理、领导力）
- self_intro: 自我介绍类
- general: 通用问题（职业规划、优缺点等）

只返回 JSON: {"type": "分类", "difficulty": "basic/intermediate/advanced"}"""

# ===== 质量评审模板 =====
REVIEW_SYSTEM_PROMPT = """你是一个严格的面试评审官。请对以下面试回答进行5维评分。

## 评分标准（每项1-5分）
1. **相关性** (relevance): 回答是否直接、完整地回应了问题
2. **STAR完整性** (star_completeness): S/T/A/R 四要素是否齐全且结构清晰
3. **优势展示度** (advantage_showcase): 是否充分展示了候选人的独特优势和能力
4. **量化密度** (quantitative_density): 是否包含具体的数字、百分比和可衡量成果
5. **真实性** (authenticity): 回答是否基于真实经历，引用是否与简历素材一致

返回 JSON 格式:
{
    "scores": {"relevance": 4, "star_completeness": 5, "advantage_showcase": 3, "quantitative_density": 4, "authenticity": 5},
    "total": 21,
    "strengths": ["STAR结构完整", "引用了具体数据"],
    "weaknesses": ["可以更突出个人独特贡献"],
    "needs_revision": false,
    "feedback": "具体的改进建议（如果需要修订）"
}"""

REVIEW_USER_TEMPLATE = Template("""## 面试问题
{{ query }}

## 候选人回答
{{ answer }}

## 简历素材（用于验证真实性）
{% for ctx in context %}
### {{ ctx.collection }}
{{ ctx.content[:300] }}
{% endfor %}

请评分并返回 JSON。""")

# ===== 自我介绍模板 =====
SELF_INTRO_SYSTEM_PROMPT = """你是一个专业的求职顾问。根据候选人的简历，生成自然流畅的自我介绍。

要求：
1. 根据目标时长调整内容详略
2. 突出与目标职位最相关的经验
3. 包含：姓名、核心技能、代表性项目、关键成果、求职意向
4. 语言简洁有力，避免陈词滥调"""

SELF_INTRO_USER_TEMPLATE = Template("""## 候选人信息
姓名: {{ profile.name }}
{% if profile.skills %}
核心技能: {% for skill in profile.skills[:8] %}{{ skill.name }}{% if not loop.last %}, {% endif %}{% endfor %}
{% endif %}

{% if profile.projects %}
## 项目经历
{% for proj in profile.projects[:3] %}
### {{ proj.name }}
- 角色: {{ proj.get('role', '开发者') }}
- 技术: {{ proj.get('tech_stack', [])|join(', ') if proj.get('tech_stack') is iterable and proj.get('tech_stack') is not string else proj.get('tech_stack', '') }}
- 成果: {{ proj.get('key_result', '') }}
{% endfor %}
{% endif %}

{% if profile.achievements %}
## 关键成就
{% for ach in profile.achievements[:3] %}
- {{ ach.description }}
{% endfor %}
{% endif %}

## 目标职位
{{ target_position or '技术岗位' }}

## 时长要求
{{ length_desc }}（约{{ word_count }}字）

请生成一段自我介绍，直接输出内容，不要加标题。""")


def _infer_project_name(ctx: Dict[str, Any]) -> str:
    """推断素材所属项目名。优先按内容文本判断（更可靠），再回退到 metadata。

    注意：source_text 可能被分块污染（视觉康复素材的 source_text 误标为 ResuMatch），
    所以以 content 内容为准匹配项目关键词。
    """
    md = ctx.get("metadata", {}) or {}
    content = str(ctx.get("content", "") or "")
    source_text = str(md.get("source_text", "") or "")

    # 项目关键词表：别名 → 项目名（内容命中优先）
    project_keywords = [
        ("视觉康复", ["视觉康复", "随访", "医疗", "康复", "多端协同"]),
        ("ResuMatch", ["ResuMatch", "网申", "面试助手", "多Agent", "检索增强", "RAG"]),
        ("PaperPilot", ["PaperPilot", "科研助手", "论文"]),
        ("MLLM", ["MLLM", "多模态摘要", "图神经网络"]),
    ]

    # 1. 内容优先：content 命中哪个项目就归哪个（防 source_text 污染）
    content_hits = [proj for proj, aliases in project_keywords if any(a in content for a in aliases)]
    if content_hits:
        return content_hits[0]

    # 2. 回退：metadata.name
    name = md.get("name", "") or ""
    if name:
        return name

    # 3. 再回退：source_text
    import re as _re
    m = _re.search(r'(ResuMatch[^\s（）()]*|PaperPilot[^\s（）()]*|视觉康复[^\s（）()]*)', source_text)
    return m.group(1) if m else ""


def _annotate_project(ctx: Dict[str, Any]) -> str:
    """给素材渲染文本，附上项目归属标注。"""
    proj = _infer_project_name(ctx)
    tag = f"[项目: {proj}] " if proj else ""
    return f"{tag}{ctx.get('content', '')}"


def build_star_prompt(state: Dict[str, Any]) -> tuple[str, str]:
    """构建 STAR 生成的 system/user prompt

    对检索素材做「项目归属标注」：每条素材前加 [项目: xxx]，
    配合 STAR_SYSTEM_PROMPT 的项目归属约束，避免 writer 跨项目混用素材。
    """
    system = STAR_SYSTEM_PROMPT
    annotated_context = [
        {**ctx, "content": _annotate_project(ctx)}
        for ctx in state.get("reranked_context", [])
    ]
    user = STAR_USER_TEMPLATE.render(
        profile=state.get("user_profile", {}),
        query=state.get("query", ""),
        reranked_context=annotated_context,
        retrieved_projects=state.get("retrieved_projects", []),
        revision_feedback=state.get("revision_feedback", ""),
    )
    return system, user


def build_review_prompt(state: Dict[str, Any]) -> tuple[str, str]:
    """构建评审的 system/user prompt"""
    system = REVIEW_SYSTEM_PROMPT
    user = REVIEW_USER_TEMPLATE.render(
        query=state.get("query", ""),
        answer=state.get("draft_answer", state.get("final_answer", "")),
        context=state.get("reranked_context", [])[:5],
    )
    return system, user


def build_self_intro_prompt(
    profile: Dict[str, Any], target_position: str, length: str
) -> tuple[str, str]:
    """构建自我介绍的 system/user prompt"""
    length_config = {
        "30s": {"desc": "约30秒口述", "words": 80},
        "1min": {"desc": "约1分钟口述", "words": 200},
        "3min": {"desc": "约3分钟口述", "words": 600},
    }
    config = length_config.get(length, length_config["1min"])

    system = SELF_INTRO_SYSTEM_PROMPT
    user = SELF_INTRO_USER_TEMPLATE.render(
        profile=profile,
        target_position=target_position,
        length_desc=config["desc"],
        word_count=config["words"],
    )
    return system, user
