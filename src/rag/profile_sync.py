"""档案 RAG 同步 — profile.json 编辑后重建向量索引

背景：上传简历时全量解析入库（parser → chunker → milvus），但档案页的
手动编辑（基本信息/技能/项目/教育/成果）只写 profile.json，向量索引
仍是旧数据——面试检索看到的始终是编辑前的内容。本模块消除这个脱节。

策略：
- 每次档案编辑保存后，从 profile.json 重建 skills/projects/achievements/
  education 四个集合（project_docs 不动——它是独立上传的项目资料）
- 产出的 Document 与 parser.to_documents 字段同构（type 复数、chunk_id
  前缀一致），并额外把档案页手动维护的 details/difficulties/challenges/
  responsibilities 写进项目 content——这正是档案编辑的核心价值，必须
  进检索
- 编辑频率低（人工操作），全量重建 + 原子替换足够，无需增量 diff

边界（CLAUDE.md LLM 边界）：本模块零 LLM——只做字段拼接，不改写内容，
拼接文本全部来自用户在档案页填写的原文。
"""
from typing import List

from src.rag.parser import Document


def profile_to_documents(profile: dict) -> List[Document]:
    """把 profile.json 转为文档块列表（与 parser.to_documents 同构 + 档案扩展字段）"""
    documents = []

    # ===== 技能 =====
    for i, s in enumerate(profile.get("skills", [])):
        name = s.get("name", "") if isinstance(s, dict) else str(s)
        category = s.get("category", "") if isinstance(s, dict) else ""
        content = f"技能: {name}"
        if category:
            content += f" (类别: {category})"
        documents.append(Document(
            content=content,
            metadata={"type": "skills", "index": i, "name": name, "category": category,
                      "source": "profile_edit"},
            chunk_id=f"skill_{i}",
        ))

    # ===== 项目（含档案页手动字段：细节/难点/挑战/职责）=====
    for i, p in enumerate(profile.get("projects", [])):
        parts = [f"项目: {p.get('name', '')}"]
        if p.get("role"):
            parts.append(f"角色: {p['role']}")
        techs = p.get("tech_stack") or []
        if techs:
            parts.append(f"技术栈: {', '.join(techs)}")
        if p.get("time_period"):
            parts.append(f"时间: {p['time_period']}")
        if p.get("key_result"):
            parts.append(f"关键成果: {p['key_result']}")
        if p.get("description"):
            parts.append(f"描述: {p['description']}")
        # 档案页手动维护的追问重点字段——面试检索的主要价值来源
        details = p.get("details") or []
        if details:
            parts.append("项目细节:\n" + "\n".join(f"- {d}" for d in details if str(d).strip()))
        difficulties = p.get("difficulties") or []
        if difficulties:
            parts.append("项目难点:\n" + "\n".join(f"- {d}" for d in difficulties if str(d).strip()))
        if p.get("challenges"):
            parts.append(f"挑战与解决: {p['challenges']}")
        if p.get("responsibilities"):
            parts.append(f"职责: {p['responsibilities']}")
        documents.append(Document(
            content="\n".join(parts),
            metadata={"type": "projects", "index": i, "name": p.get("name", ""),
                      "role": p.get("role", ""), "source": "profile_edit"},
            chunk_id=f"project_{i}",
        ))

    # ===== 成果 =====
    for i, a in enumerate(profile.get("achievements", [])):
        desc = a.get("description", "") if isinstance(a, dict) else str(a)
        documents.append(Document(
            content=f"成果: {desc}",
            metadata={"type": "achievements", "index": i, "source": "profile_edit"},
            chunk_id=f"achievement_{i}",
        ))

    # ===== 教育经历 =====
    for i, e in enumerate(profile.get("education", [])):
        parts = [f"教育: {e.get('school', '')} - {e.get('degree', '')}"]
        if e.get("major"):
            parts.append(f"专业: {e['major']}")
        if e.get("time"):
            parts.append(f"时间: {e['time']}")
        documents.append(Document(
            content="\n".join(parts),
            metadata={"type": "education", "index": i, "school": e.get("school", ""),
                      "source": "profile_edit"},
            chunk_id=f"education_{i}",
        ))

    return documents


def sync_profile_to_rag(profile: dict) -> dict:
    """档案编辑后的索引同步：重建四个集合（project_docs 保持不动）

    Returns: {"indexed": N, "collections": {...}}，失败抛异常由调用方决定降级策略
    """
    from src.rag.vector_store import get_vector_store
    from src.rag.chunker import ParentChildChunker

    documents = profile_to_documents(profile)
    if not documents:
        # 空档案：清空四集合即可（不能报错——用户可能刚删完所有条目）
        vs = get_vector_store()
        _drop_resume_collections(vs)
        return {"indexed": 0, "collections": vs.get_collection_info()}

    chunker = ParentChildChunker()
    children, _, _ = chunker.chunk_documents(documents)

    vs = get_vector_store()
    # 原子替换：先删后建。编辑频率低，不做增量（简单可靠优先）
    _drop_resume_collections(vs)
    total = vs.index_documents(children)
    return {"indexed": total, "collections": vs.get_collection_info()}


def _drop_resume_collections(vs) -> None:
    """删除简历四集合（project_docs 是按项目独立上传的资料库，不在重建范围）"""
    import chromadb  # noqa: F401  # 仅为类型语义（降级后端也存在同名 delete API）

    for name in ("skills", "projects", "achievements", "education"):
        try:
            vs.client.delete_collection(name)
        except Exception:
            pass
    # Milvus/Chroma 双后端的删除 API 名一致；删完后重建集合
    try:
        from src.rag.milvus_store import MilvusVectorStore, _ChromaFallbackStore
        if isinstance(vs, MilvusVectorStore):
            vs._ensure_collections()
        elif isinstance(vs, _ChromaFallbackStore):
            vs._ensure_collections()
    except Exception:
        pass
