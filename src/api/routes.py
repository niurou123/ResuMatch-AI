"""FastAPI 路由定义"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
import json

from src.api.schemas import (
    ResumeUploadResponse, ProfileResponse,
    InterviewRequest, InterviewResponse,
    MockInterviewStartRequest, MockInterviewStartResponse,
    MockInterviewNextRequest, MockInterviewNextResponse,
    SelfIntroRequest, SelfIntroResponse,
    JDMatchRequest, JDMatchResponse,
    FormFillRequest, FormFillResponse,
    SystemInfoResponse, HealthResponse,
)
from src.config import settings
from src.core.memory import SessionMemory

# 延迟导入（部分模块依赖 chromadb，可能未安装）
def __get_vector_store():
    from src.rag.vector_store import get_vector_store
    return _get_vector_store()

def _get_parser():
    from src.rag.parser import ResumeParser
    return _get_parser()

def _get_chunker():
    from src.rag.chunker import ParentChildChunker
    return _get_chunker()

def _run_interview_workflow(*args, **kwargs):
    from src.agents.graph import run_interview_workflow as f
    return f(*args, **kwargs)

def __run_interview_stream(*args, **kwargs):
    from src.agents.graph import run_interview_stream as f
    return f(*args, **kwargs)

router = APIRouter(prefix="/api/v1")

# 全局会话管理
_sessions: Dict[str, Any] = {}
_session_memory = SessionMemory()


# ===== 健康检查 =====
@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
    )


# ===== 简历上传 =====
@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    """上传并解析简历文件"""
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in settings.get_supported_formats():
        raise HTTPException(400, f"不支持的格式: .{ext}")

    # 保存文件
    upload_dir = Path(settings.RESUME_UPLOAD_PATH)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # 用 run_in_executor 在独立线程中执行，避免 asyncio 递归问题
        import concurrent.futures
        import asyncio
        loop = asyncio.get_event_loop()

        def do_parse(fp):
            import sys
            sys.setrecursionlimit(50000)
            from src.rag.parser import ResumeParser
            from src.rag.chunker import ParentChildChunker
            from src.rag.vector_store import get_vector_store
            p = ResumeParser()
            parsed = p.parse(fp)
            docs = p.to_documents(parsed)
            c = ParentChildChunker()
            children, _, _ = c.chunk_documents(docs)
            vs = get_vector_store()
            vs.reset()
            total = vs.index_documents(children)
            return parsed, vs.get_collection_info(), total

        parsed, collections, total = await loop.run_in_executor(
            None, do_parse, str(file_path)
        )

        profile = {
            "name": parsed.name, "email": parsed.email, "phone": parsed.phone,
            "skills": [{"name": s["name"], "category": s["category"]} for s in parsed.skills],
            "projects": [{"name": p["name"], "tech_stack": p.get("tech_stack", []), "key_result": p.get("key_result", "")} for p in parsed.projects],
            "achievements": [{"description": a.get("description", "")} for a in parsed.achievements],
            "education": parsed.education,
        }

        return ResumeUploadResponse(
            success=True, filename=file.filename, profile=profile,
            collections=collections, message=f"简历解析成功，共索引 {total} 条信息",
        )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # 截断长错误信息
        err_msg = str(e)[:300]
        print(f"[ERROR] 简历上传失败:\n{tb[-2000:]}")
        raise HTTPException(500, f"简历解析失败: {err_msg}")


@router.get("/resume/profile", response_model=ProfileResponse)
async def get_profile():
    """获取当前简历画像"""
    vector_store = _get_vector_store()
    stats = vector_store.get_collection_info()

    return ProfileResponse(
        collection_stats=stats,
        skills_count=stats.get("skills", 0),
        projects_count=stats.get("projects", 0),
        achievements_count=stats.get("achievements", 0),
    )


# ===== 面试问答 =====
@router.post("/interview/answer", response_model=InterviewResponse)
async def interview_answer(request: InterviewRequest):
    """单次面试问答"""
    import concurrent.futures
    import asyncio as aio
    loop = aio.get_event_loop()

    def do_interview(q):
        import sys, asyncio
        sys.setrecursionlimit(50000)
        async def _run():
            from src.agents.graph import run_interview_workflow
            return await run_interview_workflow(q, str(__import__('uuid').uuid4()))
        return asyncio.run(_run())

    try:
        state = await loop.run_in_executor(None, do_interview, request.question)

        return InterviewResponse(
            question=request.question,
            answer=state.get("final_answer", state.get("draft_answer", "")),
            question_type=state.get("question_type", ""),
            citations=state.get("citations", []),
            review_scores=state.get("review_scores", {}),
            review_total=state.get("review_total", 0),
            revision_count=state.get("revision_count", 0),
            error=state.get("error"),
        )

    except Exception as e:
        raise HTTPException(500, f"面试推理失败: {str(e)}")


@router.post("/interview/stream")
async def interview_stream(request: InterviewRequest):
    """流式面试问答（SSE）"""
    async def event_generator():
        async for event in _run_interview_stream(
            query=request.question,
            session_id=str(uuid.uuid4()),
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===== 模拟面试 =====
@router.post("/mock/start", response_model=MockInterviewStartResponse)
async def mock_interview_start(request: MockInterviewStartRequest):
    """开始模拟面试"""
    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = {
        "round": 0,
        "max_rounds": request.max_rounds,
        "history": [],
        "focus_areas": request.focus_areas,
        "difficulty": request.difficulty,
    }

    first_question = "你好！感谢参加今天的面试。请先做一个简短的自我介绍吧。"
    if request.focus_areas:
        areas = "、".join(request.focus_areas)
        first_question = f"你好！我看到你比较关注{areas}领域。请先简要介绍一下你自己，特别是与这些领域相关的经验。"

    return MockInterviewStartResponse(
        session_id=session_id,
        first_question=first_question,
        total_rounds=request.max_rounds,
    )


@router.post("/mock/next", response_model=MockInterviewNextResponse)
async def mock_interview_next(request: MockInterviewNextRequest):
    """下一轮追问"""
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(404, "会话不存在或已过期")

    session["round"] += 1
    session["history"].append({
        "round": session["round"],
        "answer": request.answer,
    })

    is_last = session["round"] >= session["max_rounds"]

    # 基于上下文生成追问
    next_question = "请详细说说你在项目中遇到的最大技术挑战以及你是如何解决的？"
    if is_last:
        next_question = "最后一个问题：你对未来的职业发展有什么规划？"

    return MockInterviewNextResponse(
        question=next_question,
        round_number=session["round"],
        is_last=is_last,
    )


# ===== 自我介绍 =====
@router.post("/intro/generate", response_model=SelfIntroResponse)
async def generate_intro(request: SelfIntroRequest):
    """生成自我介绍"""
    from src.core.prompts import build_self_intro_prompt
    from src.core.llm_client import get_client, Message

    vector_store = _get_vector_store()
    stats = vector_store.get_collection_info()

    if sum(stats.values()) == 0:
        raise HTTPException(400, "请先上传简历")

    client = get_client()

    async def generate_one(length: str) -> str:
        system, user = build_self_intro_prompt(
            profile={},  # 从 vector store 获取
            target_position=request.target_position,
            length=length,
        )
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=user),
        ]
        return await client.chat_sync(messages, temperature=0.7)

    # 并行生成三个版本
    import asyncio
    intro_30s, intro_1min, intro_3min = await asyncio.gather(
        generate_one("30s"),
        generate_one("1min"),
        generate_one("3min"),
    )

    return SelfIntroResponse(
        intro_30s=intro_30s,
        intro_1min=intro_1min,
        intro_3min=intro_3min,
    )


# ===== JD 匹配 =====
@router.post("/match/analyze", response_model=JDMatchResponse)
async def analyze_jd_match(request: JDMatchRequest):
    """JD-简历匹配度分析"""
    from src.rag.knowledge_graph import SkillGraph
    from src.core.llm_client import get_client, Message

    vector_store = _get_vector_store()
    stats = vector_store.get_collection_info()

    if sum(stats.values()) == 0:
        raise HTTPException(400, "请先上传简历")

    # 从 ChromaDB 获取所有技能
    all_skills = []
    skill_results = vector_store.search("", "skills", top_k=50)
    for r in skill_results:
        name = r.get("metadata", {}).get("name", "")
        if name:
            all_skills.append(name)

    # Skill Graph 分析
    graph = SkillGraph()
    gaps = graph.detect_skill_gaps(request.target_position, all_skills)

    # LLM 深度分析
    client = get_client()
    system_prompt = """你是技术招聘专家。分析JD和候选人技能的匹配度。
返回JSON: {"match_score": 0-100, "strength_analysis": "...", "gap_analysis": "...", "matched_skills": [...], "missing_skills": [...]}"""

    user_prompt = f"""## JD描述
{request.jd_text[:2000]}

## 候选人技能
{', '.join(all_skills[:20])}

## 岗位: {request.target_position}"""

    try:
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        raw = await client.chat_sync(messages, temperature=0.3)
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(match.group(0)) if match else {}
    except Exception:
        result = {}

    return JDMatchResponse(
        match_score=result.get("match_score", gaps["match_rate"] * 100),
        match_rate=gaps["match_rate"],
        matched_skills=result.get("matched_skills", []),
        missing_skills=result.get("missing_skills", gaps["recommended_skills"]),
        recommended_skills=gaps["recommended_skills"],
        missing_categories=gaps["missing_categories"],
        strength_analysis=result.get("strength_analysis", ""),
        gap_analysis=result.get("gap_analysis", ""),
    )


# ===== 智能表单填充 =====
@router.post("/form/fill")
async def smart_form_fill(req: Request):
    """LLM驱动的智能表单匹配填充"""
    from src.core.llm_client import get_client, Message
    import re

    body = await req.json()
    fields = body.get("fields", [])
    if not fields:
        return {"fill_plan": [], "total": 0}

    # 优先使用 chromaDB 中的简历数据
    profile_data = _session_memory.long_term_profile
    if not profile_data or len(profile_data) < 20:
        try:
            vs = _get_vector_store()
            info = vs.get_collection_info()
            if sum(info.values()) > 0:
                # 从 chromaDB 收集所有数据
                all_docs = []
                for coll in ["skills","projects","achievements","education"]:
                    results = vs.search("", coll, top_k=20)
                    for r in results:
                        all_docs.append(f"[{r.get('collection','')}] {r.get('content','')}")
                profile_data = "\n".join(all_docs) if all_docs else "未上传简历"
        except:
            profile_data = "未上传简历"

    if not fields:
        return {"fill_plan": [], "total": 0}

    # 格式化学段
    fields_text = json.dumps([
        {"index": i, "label": f.get("label", ""), "tag": f.get("tag", ""),
         "type": f.get("type", ""), "options": f.get("options", []),
         "placeholder": f.get("placeholder", ""), "id": f.get("id", ""),
         "required": f.get("required", False)}
        for i, f in enumerate(fields)
    ], ensure_ascii=False, indent=2)

    prompt = f"""你是专业网申表单智能填充AI。请根据用户档案，为每个表单字段生成最合适的填写值。

## 用户档案
{profile_data[:4000]}

## 表单字段（共{len(fields)}个）
{fields_text[:6000]}

## 要求
对每个字段返回填写计划：
- value: 要填入的值（优先使用档案中的数据；档案没有的，填入合理默认值如民族→汉族、政治面貌→共青团员；完全无法判断的留空）
- confidence: 匹配置信度 0-1
- fill_strategy: text/select/radio_click/datepicker
- action: auto_fill(confidence>0.7) / review(0.4-0.7) / skip(<0.4)
- reason: 简短填写理由

返回 JSON: {{"plan": [{{"index": 0, "value": "...", "confidence": 0.95, "fill_strategy": "text", "action": "auto_fill", "reason": "..."}}]}}"""

    try:
        client = get_client()
        messages = [
            Message(role="system", content="你是网申表单填充专家。只返回JSON，不要解释。"),
            Message(role="user", content=prompt),
        ]
        raw = await client.chat_sync(messages, temperature=0.3, max_tokens=4000)

        # 提取 JSON
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        result = json.loads(match.group(0)) if match else {"plan": []}
        fill_plan = result.get("plan", [])

        auto = sum(1 for p in fill_plan if p.get("action") == "auto_fill")
        review = sum(1 for p in fill_plan if p.get("action") == "review")
        skip = len(fill_plan) - auto - review

        return {
            "fill_plan": fill_plan, "total": len(fill_plan),
            "auto_count": auto, "review_count": review, "skip_count": skip,
        }

    except Exception as e:
        raise HTTPException(500, f"LLM匹配失败: {str(e)}")


# ===== 系统信息 =====
@router.get("/system/info", response_model=SystemInfoResponse)
async def system_info():
    vector_store = _get_vector_store()
    return SystemInfoResponse(
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        model=settings.DEEPSEEK_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        collections=vector_store.get_collection_info(),
        memory_stats=_session_memory.get_stats(),
    )
