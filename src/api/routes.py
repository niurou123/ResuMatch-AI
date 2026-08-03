"""FastAPI 路由定义 - 多Agent架构 v3.0"""
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
    ProfileDetailResponse, ProfileUpdateProjectRequest,
    ProfileUpdateSkillsRequest, ProfileMessageResponse,
    InterviewRequest, InterviewResponse,
    MockInterviewStartRequest, MockInterviewStartResponse,
    MockInterviewNextRequest, MockInterviewNextResponse,
    MockSuggestRequest, MockSuggestResponse, MockProjectsResponse,
    SelfIntroRequest, SelfIntroResponse,
    JDMatchRequest, JDMatchResponse,
    ProjectMatchRequest, ProjectMatchResponse,
    FormFillRequest, FormFillResponse,
    SystemInfoResponse, HealthResponse,
)
from src.config import settings
from src.core.memory import SessionMemory

# 延迟导入（部分模块依赖 chromadb，可能未安装）
def _get_vector_store():
    from src.rag.vector_store import get_vector_store
    return get_vector_store()

def _run_interview_workflow(*args, **kwargs):
    from src.agents.graph import run_interview_workflow as f
    return f(*args, **kwargs)

def _run_interview_stream(*args, **kwargs):
    from src.agents.graph import run_interview_stream as f
    return f(*args, **kwargs)

router = APIRouter(prefix="/api/v1")

# 全局会话管理
_sessions: Dict[str, Any] = {}
_session_memory = SessionMemory()


async def _generate_mock_answer(question: str, profile: dict, project: str = "") -> dict:
    """生成面试对练的 AI 候选人回答（单次 LLM 调用，快且稳）。

    与完整多Agent工作流不同，这里用一次 LLM 调用完成：
    - 基于简历真实素材生成 STAR 回答
    - 检索目标项目的 RAG 资料文档（如有），基于真实文档作答
    - 简历未覆盖的技术细节，基于通用框架知识推理补充（不编造简历没有的量化成果）

    返回 {answer, question_type, citations}
    """
    try:
        from src.core.llm_client import get_client, Message

        # 汇总简历已知技能/项目
        known_skills, known_projects = [], []
        for sk in profile.get("skills", [])[:15]:
            name = sk.get("name") if isinstance(sk, dict) else str(sk)
            if name:
                known_skills.append(name)
        for p in profile.get("projects", [])[:4]:
            if isinstance(p, dict) and p.get("name"):
                techs = p.get("tech_stack") or []
                desc = p.get("description", "") or ""
                challenges = p.get("challenges", "") or ""
                responsibilities = p.get("responsibilities", "") or ""
                details = p.get("details") or []
                difficulties = p.get("difficulties") or []
                line = f"- {p['name']}（角色:{p.get('role','')}，技术:{', '.join(techs[:8])}，成果:{p.get('key_result','')[:80]}）"
                if desc:
                    line += f"\n  项目描述: {desc[:150]}"
                if responsibilities:
                    line += f"\n  职责: {responsibilities[:150]}"
                if details:
                    line += f"\n  项目细节: {'；'.join(str(d)[:60] for d in details[:5])}"
                if difficulties:
                    line += f"\n  项目难点: {'；'.join(str(d)[:60] for d in difficulties[:5])}"
                if challenges:
                    line += f"\n  挑战与解决: {challenges[:150]}"
                known_projects.append(line)
        skills_text = "、".join(dict.fromkeys(known_skills)) or "（简历暂未上传）"
        projects_text = "\n".join(known_projects) or "（暂无项目）"

        # ===== 项目 RAG 资料检索 =====
        # 确定目标项目：优先请求指定，其次从问题匹配项目名
        target_project = project.strip()
        if not target_project:
            for p in profile.get("projects", []):
                if isinstance(p, dict) and p.get("name") and p["name"] in question:
                    target_project = p["name"]
                    break
        project_refs = ""
        if target_project:
            try:
                from src.rag.vector_store import get_vector_store
                vs = get_vector_store()
                results = vs.search(question, "project_docs", top_k=5, where={"project_name": target_project})
                if results:
                    parts = [f"[{target_project} 资料文档]"]
                    for r in results:
                        c = (r.get("content") or "").strip()
                        if c:
                            parts.append(c[:400])
                    project_refs = "\n".join(parts)
            except Exception:
                project_refs = ""
        if project_refs:
            refs_section = f"\n## 该项目参考资料（来自上传的文档，回答应优先采用）\n{project_refs}\n"
        else:
            refs_section = ""

        system_prompt = """你是专业的AI面试助手，为候选人生成面试回答。候选人简历素材可能不完整。

## 核心原则
1. **STAR结构**: 严格按 Situation → Task → Action → Result 组织
2. **真实性**: 简历明确记载的内容正常陈述；简历未记载的具体细节，基于该技术的通用框架知识做**合理推理阐述**
3. **区分来源**: 简历记载的 → 正常说；基于推理的 → 用"基于我对XX的理解""通常做法是"等表述
4. **禁止编造量化成果**: 简历没有的具体数字/百分比/时间线不得虚构；没有就说"简历未记录具体量化指标"
5. **第一人称** "我"叙述

## 覆盖规则
- 若问题涉及的技术在简历技能/项目中出现 → 结合真实经历回答
- 若技术简历未出现，但属于候选人技术栈相关的通用知识 → 基于框架知识推理回答，明确标注是推理
- 不要因为简历素材缺失就拒绝回答，要用推理给出有价值的内容"""
        user_prompt = f"""## 候选人简历技能
{skills_text}

## 候选人项目经历
{projects_text}
{refs_section}
## 面试官的问题
{question}

请生成第一人称的 STAR 面试回答。"""

        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        answer = await client.chat_sync(messages, temperature=0.6, max_tokens=900)
        answer = (answer or "").strip()
        return {
            "answer": answer,
            "question_type": "STAR",
            "citations": [],
        }
    except Exception as e:
        import traceback
        print(f"[ERROR] _generate_mock_answer:\n{traceback.format_exc()}")
        return {"answer": "", "question_type": "", "citations": []}


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
    """上传并解析简历文件 — v2.0 带来源追踪和验证报告"""
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

        # 构建带来源追踪的 profile
        profile = {
            "name": parsed.name,
            "email": parsed.email,
            "phone": parsed.phone,
            "skills": [
                {
                    "name": s["name"],
                    "category": s.get("category", "other"),
                    "confidence": s["_source"].confidence if s.get("_source") else 0,
                    "source_line": s["_source"].source_line_start if s.get("_source") else 0,
                }
                for s in parsed.skills
            ],
            "projects": [
                {
                    "name": p["name"],
                    "role": p.get("role", ""),
                    "tech_stack": p.get("tech_stack", []),
                    "time_period": p.get("time_period", ""),
                    "key_result": p.get("key_result", ""),
                    "description": p.get("description", ""),
                    "details": p.get("details", ""),
                    "difficulties": p.get("difficulties", ""),
                    "challenges": p.get("challenges", ""),
                    "responsibilities": p.get("responsibilities", ""),
                    "confidence": p["_source"].confidence if p.get("_source") else 0,
                }
                for p in parsed.projects
            ],
            "achievements": [
                {
                    "description": a.get("description", ""),
                    "confidence": a["_source"].confidence if a.get("_source") else 0,
                }
                for a in parsed.achievements
            ],
            "education": [
                {
                    "school": e.get("school", ""),
                    "degree": e.get("degree", ""),
                    "major": e.get("major", ""),
                    "time": e.get("time", ""),
                    "confidence": e["_source"].confidence if e.get("_source") else 0,
                }
                for e in parsed.education
            ],
        }

        # 结构化档案落盘（项目库持久化，供项目-JD 匹配引擎读取）
        try:
            from src.features.profile_store import ProfileStore
            ProfileStore.save(profile)
        except Exception as e:
            print(f"[WARN] 项目库落盘失败: {e}")

        # 提取统计（用于用户验证）
        stats = parsed.extraction_stats
        verification = {
            "raw_text_hash": parsed.raw_text_hash,
            "raw_text_length": stats.raw_text_length if stats else 0,
            "total_extracted": (
                (stats.total_skills_found if stats else 0) +
                (stats.total_projects_found if stats else 0) +
                (stats.total_achievements_found if stats else 0)
            ),
            "high_confidence": stats.high_confidence_count if stats else 0,
            "medium_confidence": stats.medium_confidence_count if stats else 0,
            "low_confidence": stats.low_confidence_count if stats else 0,
            "sections_found": stats.sections_identified if stats else [],
            "verification_report": parsed.get_verification_summary(),
        }

        # 字段来源追踪（供前端逐项对比）
        field_sources = parsed.get_field_sources()[:20]

        return ResumeUploadResponse(
            success=True,
            filename=file.filename,
            profile=profile,
            collections=collections,
            message=f"简历解析成功，共提取 {verification['total_extracted']} 条信息（高置信度: {verification['high_confidence']}, 中: {verification['medium_confidence']}, 低: {verification['low_confidence']}）",
            verification=verification,
            field_sources=field_sources,
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


# ===== 档案管理 =====
@router.get("/profile", response_model=ProfileDetailResponse)
async def get_profile_detail():
    """获取完整档案（供档案编辑页查看/编辑）"""
    from src.features.profile_store import ProfileStore
    profile = ProfileStore.load()
    # 兼容旧数据：给项目补充缺失的扩展字段
    for p in profile.get("projects", []):
        p.setdefault("description", "")
        p.setdefault("details", [])
        p.setdefault("difficulties", [])
        p.setdefault("challenges", "")
        p.setdefault("responsibilities", "")
    return ProfileDetailResponse(profile=profile)


@router.put("/profile/projects", response_model=ProfileMessageResponse)
async def update_project(request: ProfileUpdateProjectRequest):
    """新增或更新一个项目（project_index=-1 新增，>=0 更新）"""
    from src.features.profile_store import ProfileStore
    profile = ProfileStore.load()
    projects = profile.get("projects", [])

    new_project = {
        "name": request.name,
        "role": request.role,
        "tech_stack": request.tech_stack,
        "time_period": request.time_period,
        "key_result": request.key_result,
        "description": request.description,
        "details": request.details,
        "difficulties": request.difficulties,
        "challenges": request.challenges,
        "responsibilities": request.responsibilities,
    }
    if not new_project["name"].strip():
        raise HTTPException(400, "项目名称不能为空")

    idx = request.project_index
    if idx >= 0 and idx < len(projects):
        projects[idx] = {**projects[idx], **new_project}  # 保留 confidence 等旧字段
    else:
        projects.append(new_project)

    profile["projects"] = projects
    ProfileStore.save(profile)
    return ProfileMessageResponse(success=True, message="项目已保存")


@router.delete("/profile/projects", response_model=ProfileMessageResponse)
async def delete_project(project_index: int = -1):
    """删除指定下标项目"""
    from src.features.profile_store import ProfileStore
    profile = ProfileStore.load()
    projects = profile.get("projects", [])
    if project_index < 0 or project_index >= len(projects):
        raise HTTPException(400, "项目下标无效")
    removed = projects.pop(project_index)
    profile["projects"] = projects
    ProfileStore.save(profile)
    return ProfileMessageResponse(success=True, message=f"已删除项目: {removed.get('name', '')}")


@router.put("/profile/skills", response_model=ProfileMessageResponse)
async def update_skills(request: ProfileUpdateSkillsRequest):
    """整体替换技能列表"""
    from src.features.profile_store import ProfileStore
    profile = ProfileStore.load()
    # 技能可能是 dict（旧）或 str；统一存 {name, category}
    skills = []
    for s in request.skills:
        if isinstance(s, str) and s.strip():
            skills.append({"name": s.strip(), "category": "manual"})
        elif isinstance(s, dict) and s.get("name"):
            skills.append({"name": s["name"], "category": s.get("category", "manual")})
    profile["skills"] = skills
    ProfileStore.save(profile)
    return ProfileMessageResponse(success=True, message=f"已保存 {len(skills)} 项技能")


# ===== 项目资料库（RAG 文档） =====
@router.post("/project/{project_name}/docs")
async def upload_project_doc(project_name: str, file: UploadFile = File(...)):
    """上传项目资料文档（md/txt/docx/pdf），分块存入 RAG，供面试回答检索"""
    import sys
    sys.setrecursionlimit(50000)

    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in settings.get_supported_formats():
        raise HTTPException(400, f"不支持的格式: .{ext}")

    # 读取原始文本（复用 parser 提取逻辑：pdf/docx 特殊处理，md/txt 直读）
    content = await file.read()
    try:
        from src.rag.parser import ResumeParser
        p = ResumeParser()
        raw_text = p._extract_text_bytes(content, ext)
    except Exception as e:
        # 兜底：按 utf-8 直读
        try:
            raw_text = content.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(400, f"无法读取文档: {str(e)[:100]}")

    if not raw_text or len(raw_text.strip()) < 20:
        raise HTTPException(400, "文档内容过短，无法索引")

    # 分块 + 入库（追加，不 reset）
    from src.rag.chunker import ParentChildChunker
    from src.rag.vector_store import get_vector_store
    from src.rag.parser import Document
    import uuid

    chunker = ParentChildChunker()
    doc = Document(content=raw_text, metadata={"type": "project_docs", "project_name": project_name})
    children, _, _ = chunker.chunk_documents([doc])

    docs = []
    for i, ch in enumerate(children):
        if not ch.content.strip():
            continue
        docs.append(Document(
            content=ch.content,
            metadata={
                "type": "project_docs",
                "project_name": project_name,
                "filename": file.filename,
            },
            chunk_id=f"projdoc_{uuid.uuid4().hex[:8]}_{i}",
        ))

    vs = get_vector_store()
    total = vs.index_documents(docs)
    return {"success": True, "message": f"已索引 {total} 个片段", "indexed": total, "filename": file.filename}


@router.get("/project/{project_name}/docs")
async def list_project_docs(project_name: str):
    """列出项目的资料文档清单"""
    from src.rag.vector_store import get_vector_store
    vs = get_vector_store()
    results = vs.search("", "project_docs", top_k=200, where={"project_name": project_name})
    filenames = []
    seen = set()
    for r in results:
        fn = (r.get("metadata") or {}).get("filename", "")
        if fn and fn not in seen:
            seen.add(fn)
            filenames.append(fn)
    return {"project": project_name, "documents": filenames}


@router.post("/project/{project_name}/docs/search")
async def search_project_docs(project_name: str, request: Request):
    """检索项目资料文档（按问题返回相关片段）"""
    from src.rag.vector_store import get_vector_store
    body = await request.json()
    query = (body.get("query") or "").strip()
    if not query:
        return {"results": []}
    vs = get_vector_store()
    results = vs.search(query, "project_docs", top_k=5, where={"project_name": project_name})
    return {
        "results": [
            {"content": r.get("content", ""), "score": r.get("score", 0)}
            for r in results
        ]
    }


# ===== 面试问答 =====
@router.post("/interview/answer", response_model=InterviewResponse)
async def interview_answer(request: InterviewRequest):
    """单次面试问答"""
    import sys
    sys.setrecursionlimit(50000)

    try:
        from src.agents.graph import run_interview_workflow

        # 读取当前简历画像作为 user_profile
        profile = {}
        try:
            from src.rag.vector_store import get_vector_store
            vs = get_vector_store()
            info = vs.get_collection_info()
            if sum(info.values()) > 0:
                # 收集所有已索引的文档作为用户画像
                all_docs = {}
                for coll in ["skills", "projects", "achievements", "education"]:
                    results = vs.search("", coll, top_k=50)
                    for r in results:
                        all_docs[r.get("id", "")] = {
                            "content": r.get("content", ""),
                            "collection": r.get("collection", ""),
                            "metadata": r.get("metadata", {}),
                        }
                profile["indexed_docs"] = list(all_docs.values())
                profile["name"] = "候选人"
                profile["collections"] = info
        except Exception:
            pass

        state = await run_interview_workflow(
            request.question,
            str(uuid.uuid4()),
            user_profile=profile,
        )

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
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR] interview_answer: {tb}")
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
    """开始模拟面试（AI 候选人模式：你当面试官提问，AI 基于简历回答）"""
    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = {
        "round": 0,
        "max_rounds": request.max_rounds,
        "history": [],
        "focus_areas": request.focus_areas,
        "difficulty": request.difficulty,
    }

    first_question = ""
    hint = "你作为面试官，可以开始提问了。AI 候选人将基于你的简历素材作答。"
    if request.focus_areas:
        areas = "、".join(request.focus_areas)
        hint = f"你作为面试官，可以围绕 {areas} 领域提问。AI 候选人将基于你的简历素材作答。"

    return MockInterviewStartResponse(
        session_id=session_id,
        first_question=first_question,
        total_rounds=request.max_rounds,
        message=hint,
    )


@router.post("/mock/next", response_model=MockInterviewNextResponse)
async def mock_interview_next(request: MockInterviewNextRequest):
    """面试官提问 → AI 候选人基于简历生成 STAR 回答"""
    session = _sessions.get(request.session_id)
    if not session:
        raise HTTPException(404, "会话不存在或已过期")

    # 面试官的问题（优先新字段 question，兼容旧 answer）
    question = (request.question or request.answer or "").strip()
    if not question:
        raise HTTPException(400, "请先输入面试问题")

    session["round"] += 1
    session["history"].append({
        "round": session["round"],
        "question": question,
        "answer": "",  # AI 回答在下方生成后填充
    })

    is_last = session["round"] >= session["max_rounds"]

    # 用多Agent工作流生成 AI 候选人回答（基于简历素材，含项目归属约束）
    ai_answer = ""
    question_type = ""
    citations = []
    review_scores = {}
    review_total = 0.0
    revision_count = 0
    try:
        import sys
        sys.setrecursionlimit(50000)
        from src.agents.graph import run_interview_workflow

        # 读取简历画像（技能/项目）
        profile = {}
        try:
            from src.features.profile_store import ProfileStore
            stored = ProfileStore.load()
            if stored:
                profile = stored
            else:
                from src.rag.vector_store import get_vector_store
                vs = get_vector_store()
                info = vs.get_collection_info()
                if sum(info.values()) > 0:
                    skills, projects = [], []
                    for r in vs.search("", "skills", top_k=30):
                        n = (r.get("metadata") or {}).get("name", "")
                        if n:
                            skills.append({"name": n})
                    for r in vs.search("", "projects", top_k=20):
                        md = r.get("metadata") or {}
                        content = r.get("content", "") or ""
                        if md.get("name"):
                            projects.append({
                                "name": md.get("name", ""),
                                "role": md.get("role", ""),
                                "tech_stack": [],
                                "key_result": "",
                                "description": content,
                            })
                    profile["skills"] = skills
                    profile["projects"] = projects
        except Exception:
            pass

        # 用专用单次 LLM 调用生成回答（快且稳，含技术推理退路 + 项目文档检索）
        gen = await _generate_mock_answer(question, profile, project=request.project or "")
        ai_answer = gen.get("answer", "")
        question_type = gen.get("question_type", "")
        citations = gen.get("citations", [])
        review_scores = {}
        review_total = 0
        revision_count = 0

        if not ai_answer:
            ai_answer = "抱歉，回答生成失败，请重试。"
    except Exception as e:
        import traceback
        print(f"[ERROR] mock_interview_next:\n{traceback.format_exc()}")
        ai_answer = f"生成回答时出错: {str(e)[:200]}"

    # 更新会话历史
    session["history"][-1]["answer"] = ai_answer

    return MockInterviewNextResponse(
        question=question,
        round_number=session["round"],
        is_last=is_last,
        ai_answer=ai_answer,
        question_type=question_type,
        citations=citations,
        review_scores=review_scores,
        review_total=review_total,
        revision_count=revision_count,
    )


@router.get("/mock/projects", response_model=MockProjectsResponse)
async def mock_projects():
    """返回简历项目列表（供前端选择生成问题的目标项目）"""
    projects = []
    try:
        from src.features.profile_store import ProfileStore
        for p in ProfileStore.get_projects():
            name = p.get("name", "").strip()
            if name and name not in projects:
                projects.append(name)
        if not projects:
            from src.rag.vector_store import get_vector_store
            vs = get_vector_store()
            for r in vs.search("", "projects", top_k=30):
                name = (r.get("metadata") or {}).get("name", "").strip()
                if name and name not in projects:
                    projects.append(name)
    except Exception:
        pass
    return MockProjectsResponse(projects=projects[:10])


@router.post("/mock/suggest", response_model=MockSuggestResponse)
async def mock_suggest_question(request: MockSuggestRequest):
    """AI 生成问题：支持选择项目 + 追问/新问题两种模式"""
    session = _sessions.get(request.session_id)
    history = session.get("history", []) if session else []
    mode = request.mode or "followup"
    target_project = (request.project or "").strip()

    # 读取简历素材（技能/项目/成果）作为生成依据
    resume_context = ""
    try:
        from src.rag.vector_store import get_vector_store
        vs = get_vector_store()
        info = vs.get_collection_info()
        if sum(info.values()) > 0:
            parts = []
            for coll in ["skills", "projects", "achievements", "education"]:
                results = vs.search("", coll, top_k=15)
                for r in results:
                    content = (r.get("content") or "").strip()
                    if content and not content.startswith(f"{coll} #"):
                        parts.append(f"[{coll}] {content[:120]}")
            resume_context = "\n".join(parts[:30])
    except Exception:
        pass

    # 指定了项目：优先用该项目素材，并把素材范围收窄到该项目
    project_context = ""
    if target_project:
        try:
            from src.rag.vector_store import get_vector_store
            vs = get_vector_store()
            for coll in ["projects", "achievements"]:
                for r in vs.search(target_project, coll, top_k=15):
                    content = (r.get("content") or "").strip()
                    if content and (target_project in content or target_project in str((r.get("metadata") or {}).get("name", ""))):
                        project_context += f"[{coll}] {content[:200]}\n"
        except Exception:
            pass

    # 构造历史问答上下文
    if history:
        history_text = "\n".join([
            f"第{h['round']}轮 问题: {h['question'][:100]}\n回答: {h['answer'][:150]}"
            for h in history[-3:]  # 最近3轮
        ])
    else:
        history_text = "（尚无问答，面试刚开始）"

    focus = "、".join(request.focus_areas) if request.focus_areas else "不限定"

    # 按模式构建 system prompt
    if mode == "new":
        system_prompt = """你是资深面试官助手。面试官想开启一个**全新话题**的问题（不一定基于上一轮回答）。

## 要求
1. 围绕指定项目/关注领域，提出一个**新角度**的面试问题
2. 可选角度：技术深度（架构/性能/难点）、项目细节（角色/决策/复盘）、行为（协作/冲突/成长）、系统设计
3. 直接输出一个完整、自然的面试问题（20-60字），不要解释"""
    else:  # followup 追问
        system_prompt = """你是资深面试官助手。面试官想要一个**针对性的追问**（紧扣上下文深挖）。

## 要求
1. 结合已有问答上下文，提出一个**深挖候选人能力**的追问
2. 追问应紧扣上一轮回答中**未展开的点**（技术细节、量化成果、决策过程、遇到的坑）
3. 直接输出一个完整、自然的面试问题（20-60字），不要解释
4. 若无上下文：从简历素材中选择一个最值得深挖的方向自由发挥"""

    # 项目范围说明
    if target_project:
        project_note = f"目标项目：{target_project}\n该项目素材：\n{project_context[:1500] if project_context else '（未检索到该项目素材）'}"
    else:
        project_note = "目标项目：不限（可从全部简历素材中选择）"

    user_prompt = f"""## 候选人简历素材
{resume_context[:2000] if resume_context else '（暂未上传简历或素材为空）'}

## {project_note}

## 已有问答上下文
{history_text}

## 关注领域
{focus}

## 模式
{'【新问题】开启一个全新话题' if mode == 'new' else '【追问】紧扣上下文深挖'}

请生成一个面试问题。"""

    try:
        from src.core.llm_client import get_client, Message
        client = get_client()
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        question = ""
        # 生成并校验：LLM 偶发空/过短/非问题内容时重试一次
        for _ in range(2):
            raw = await client.chat_sync(messages, temperature=0.8, max_tokens=200)
            q = (raw or "").strip().strip('"').strip("'").strip("`")
            # 清理多余前缀/换行，只保留一行有效问题
            q = q.split("\n")[0].strip()
            # 去掉可能的 "问题：" 前缀
            q = q.replace("问题：", "").replace("追问：", "").replace("Question:", "").strip()
            # 去掉 "。?" 等结尾标点前残留
            if q and not q.endswith(("？", "?", "。")):
                q += "？"
            if len(q) >= 25:  # 有效问题长度阈值（避免过短的不完整问题）
                question = q
                break

        # 生成依据说明
        if mode == "new":
            reason = f"新问题·{target_project if target_project else '不限项目'}"
        else:
            reason = "追问·" + ("上一轮回答的未展开点" if history else "简历素材中最值得深挖的方向")
            if target_project:
                reason += f"·{target_project}"
        return MockSuggestResponse(question=question, reason=reason)
    except Exception as e:
        import traceback
        print(f"[ERROR] mock_suggest_question:\n{traceback.format_exc()}")
        # 降级：返回规则化追问
        fallback = "请详细说说你在这个项目中最具挑战性的一项工作，以及你是如何解决的？"
        return MockSuggestResponse(question=fallback, reason="规则化兜底（LLM不可用）")


# ===== 自我介绍 =====
@router.post("/intro/generate", response_model=SelfIntroResponse)
async def generate_intro(request: SelfIntroRequest):
    """生成自我介绍"""
    from src.core.llm_client import get_client, Message

    vector_store = _get_vector_store()
    stats = vector_store.get_collection_info()

    if sum(stats.values()) == 0:
        raise HTTPException(400, "请先上传简历")

    # 从 ChromaDB 读取真实简历数据
    profile = {}
    all_docs = []
    for coll in ["skills", "projects", "achievements", "education"]:
        results = vector_store.search("", coll, top_k=50)
        for r in results:
            all_docs.append({
                "content": r.get("content", ""),
                "collection": r.get("collection", ""),
                "name": r.get("metadata", {}).get("name", ""),
            })

    # 组织 profile 数据
    profile["name"] = "候选人"
    profile["skills"] = [
        {"name": d["name"]}
        for d in all_docs if d["collection"] == "skills" and d["name"]
    ]
    profile["projects"] = [
        {"name": d["name"], "key_result": d["content"][:300]}
        for d in all_docs if d["collection"] == "projects" and d["name"]
    ]
    profile["achievements"] = [
        {"description": d["content"]}
        for d in all_docs if d["collection"] == "achievements"
    ]
    profile["education"] = [
        {"description": d["content"]}
        for d in all_docs if d["collection"] == "education"
    ]

    client = get_client()

    async def generate_one(length: str) -> str:
        system_prompt = """你是专业的求职顾问。请根据候选人的真实简历，生成自然流畅的自我介绍。

严格要求:
1. 只能使用下面提供的简历素材中的信息，绝不编造
2. 如果简历中某项信息不存在，直接跳过，不要说"可能"、"大概"
3. 包含：姓名(如果有)、核心技能(来自素材)、代表性项目(来自素材)、关键成果(来自素材)
4. 根据时长要求控制详略程度"""
        user_prompt = f"""## 候选人简历素材

姓名: {profile.get('name', '')}

### 技能
{chr(10).join(['- ' + s['name'] for s in profile.get('skills', [])[:15]])}

### 项目经验
{chr(10).join(['- ' + p['name'] + ': ' + p['key_result'][:200] for p in profile.get('projects', [])[:3]])}

### 关键成果
{chr(10).join(['- ' + a['description'][:200] for a in profile.get('achievements', [])[:3]])}

### 教育背景
{chr(10).join(['- ' + e['description'][:150] for e in profile.get('education', [])[:2]])}

## 目标职位: {request.target_position or '技术岗位'}
## 时长: {length} (30s约80字, 1min约200字, 3min约600字)

请生成自我介绍，直接输出，不加标题。"""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
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


# ===== 项目-JD 匹配 =====
@router.post("/match/projects", response_model=ProjectMatchResponse)
async def analyze_project_match(request: ProjectMatchRequest):
    """项目-JD 智能匹配：JD需求提取 + 三维度项目匹配 + 针对性生成"""
    from src.features.project_matcher import ProjectJDMatchService

    vector_store = _get_vector_store()

    try:
        service = ProjectJDMatchService()
        result = await service.analyze(
            request.jd_text,
            target_position=request.target_position,
            vs=vector_store,
        )
        return ProjectMatchResponse(**result)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR] analyze_project_match: {tb}")
        return ProjectMatchResponse(
            message=f"项目匹配分析失败: {str(e)[:200]}",
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
