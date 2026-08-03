"""API 请求/响应 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ===== 简历相关 =====
class ResumeUploadResponse(BaseModel):
    """简历上传响应 — v2.0 带来源追踪和验证报告"""
    success: bool
    filename: str
    profile: Dict[str, Any] = {}
    collections: Dict[str, int] = {}
    message: str = ""
    verification: Dict[str, Any] = {}    # 提取验证报告
    field_sources: list = []             # 字段来源追踪


class ProfileResponse(BaseModel):
    """简历画像响应"""
    name: str = ""
    email: str = ""
    skills_count: int = 0
    projects_count: int = 0
    achievements_count: int = 0
    profile: Dict[str, Any] = {}
    collection_stats: Dict[str, int] = {}


# ===== 档案管理 =====
class ProfileDetailResponse(BaseModel):
    """完整档案响应（供档案编辑页）"""
    profile: Dict[str, Any] = {}


class ProfileUpdateProjectRequest(BaseModel):
    """新增或更新单个项目"""
    project_index: int = -1   # -1=新增；>=0=更新该下标项目
    name: str
    role: str = ""
    tech_stack: list = []
    time_period: str = ""
    key_result: str = ""
    description: str = ""
    details: list = []           # 项目细节（分点列表：1. 2. 3. ...）
    difficulties: list = []      # 项目难点问题（分点列表：1. 2. 3. ...）
    challenges: str = ""
    responsibilities: str = ""


class ProfileUpdateSkillsRequest(BaseModel):
    """整体替换技能列表"""
    skills: list = []


class ProfileMessageResponse(BaseModel):
    """档案操作响应"""
    success: bool = True
    message: str = ""


# ===== 面试相关 =====
class InterviewRequest(BaseModel):
    """面试请求"""
    question: str
    mode: str = "interview"
    temperature: float = 0.7


class InterviewResponse(BaseModel):
    """面试响应"""
    question: str
    answer: str
    question_type: str = ""
    citations: List[Dict[str, Any]] = []
    review_scores: Dict[str, float] = {}
    review_total: float = 0.0
    revision_count: int = 0
    error: Optional[str] = None


class StreamEvent(BaseModel):
    """流式事件"""
    type: str  # chunk, review, revision_start, done, error
    content: str = ""
    scores: Dict[str, float] = {}
    total: float = 0.0
    needs_revision: bool = False
    final_answer: str = ""
    count: int = 0


# ===== 模拟面试相关 =====
class MockInterviewStartRequest(BaseModel):
    """开始模拟面试请求"""
    focus_areas: List[str] = []  # 关注领域
    difficulty: str = "intermediate"
    max_rounds: int = 5


class MockInterviewStartResponse(BaseModel):
    """开始模拟面试响应"""
    session_id: str
    first_question: str
    total_rounds: int = 5
    message: str = ""


class MockInterviewNextRequest(BaseModel):
    """下一轮追问请求（面试官提问，AI 候选人回答）"""
    session_id: str
    question: str   # 面试官的问题
    answer: str = ""  # 兼容旧字段
    project: str = ""  # 目标项目（可选，指定则优先检索该项目 RAG 文档）


class MockInterviewNextResponse(BaseModel):
    """下一轮追问响应"""
    question: str
    round_number: int
    previous_feedback: Dict[str, Any] = {}
    is_last: bool = False
    session_summary: Optional[str] = None
    ai_answer: str = ""        # AI 候选人基于简历的 STAR 回答
    question_type: str = ""    # 问题类型（技术/项目/行为/通用）
    citations: List[Dict[str, Any]] = []
    review_scores: Dict[str, float] = {}
    review_total: float = 0.0
    revision_count: int = 0


class MockSuggestRequest(BaseModel):
    """AI 生成追问请求（面试官不知道问什么时）"""
    session_id: str
    focus_areas: List[str] = []  # 关注领域
    project: str = ""            # 指定项目名（可选，空则从全部简历素材生成）
    mode: str = "followup"       # followup=基于上下文追问 / new=开启新话题的问题


class MockSuggestResponse(BaseModel):
    """AI 生成追问响应"""
    question: str = ""
    reason: str = ""   # 生成依据说明（简短）


class MockProjectsResponse(BaseModel):
    """简历项目列表响应"""
    projects: List[str] = []


# ===== 自我介绍相关 =====
class SelfIntroRequest(BaseModel):
    """自我介绍请求"""
    target_position: str = ""
    target_company: str = ""
    length: str = "1min"  # 30s, 1min, 3min


class SelfIntroResponse(BaseModel):
    """自我介绍响应"""
    intro_30s: str = ""
    intro_1min: str = ""
    intro_3min: str = ""


# ===== 智能表单填充 =====
class FormFillRequest(BaseModel):
    """智能表单填充请求"""
    fields: list = []     # 扫描到的表单字段
    url: str = ""          # 页面URL

    class Config:
        extra = "allow"


class FormFillResponse(BaseModel):
    """智能表单填充响应"""
    fill_plan: list = []   # 填充计划
    total: int = 0
    auto_count: int = 0
    review_count: int = 0
    skip_count: int = 0


# ===== JD 匹配相关 =====
class JDMatchRequest(BaseModel):
    """JD 匹配请求"""
    jd_text: str
    target_position: str = ""


class JDMatchResponse(BaseModel):
    """JD 匹配响应"""
    match_score: float = 0.0  # 0-100
    match_rate: float = 0.0   # 0-1
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    recommended_skills: List[str] = []
    missing_categories: List[str] = []
    strength_analysis: str = ""
    gap_analysis: str = ""


# ===== 项目-JD 匹配相关 =====
class ProjectMatchRequest(BaseModel):
    """项目-JD 匹配请求"""
    jd_text: str
    target_position: str = ""


class ProjectMatchResponse(BaseModel):
    """项目-JD 匹配响应 — 三维度项目匹配 + 针对性生成"""
    jd_requirements: Dict[str, Any] = {}   # JD 需求提取结果
    projects: List[Dict[str, Any]] = []    # 排序后的项目匹配明细
    top_project: Optional[Dict[str, Any]] = None
    targeted_answer: str = ""              # 针对性 STAR 面试回答
    targeted_resume_desc: str = ""         # 针对性简历项目描述
    resume_content: str = ""               # 针对性完整简历内容（技术栈增强+项目描述）
    added_skills: List[str] = []           # 建议新增的技术栈（JD要求但简历缺失）
    matched_skills: List[str] = []
    missing_skills: List[str] = []
    message: str = ""


# ===== 系统相关 =====
class SystemInfoResponse(BaseModel):
    """系统信息响应"""
    app_name: str
    version: str
    model: str
    embedding_model: str
    collections: Dict[str, int] = {}
    memory_stats: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    app: str
    version: str
