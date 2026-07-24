"""API 请求/响应 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ===== 简历相关 =====
class ResumeUploadResponse(BaseModel):
    """简历上传响应"""
    success: bool
    filename: str
    profile: Dict[str, Any] = {}
    collections: Dict[str, int] = {}
    message: str = ""


class ProfileResponse(BaseModel):
    """简历画像响应"""
    name: str = ""
    email: str = ""
    skills_count: int = 0
    projects_count: int = 0
    achievements_count: int = 0
    profile: Dict[str, Any] = {}
    collection_stats: Dict[str, int] = {}


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


class MockInterviewNextRequest(BaseModel):
    """下一轮追问请求"""
    session_id: str
    answer: str


class MockInterviewNextResponse(BaseModel):
    """下一轮追问响应"""
    question: str
    round_number: int
    previous_feedback: Dict[str, Any] = {}
    is_last: bool = False
    session_summary: Optional[str] = None


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
