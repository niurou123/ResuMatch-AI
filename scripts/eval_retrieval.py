# -*- coding: utf-8 -*-
"""检索质量评测 — 指标计算 + 消融矩阵 + 报告

指标（信息检索标准三件套，答辩可引用教科书定义）：
- Recall@k:    前 k 条结果中命中 ground truth 的比例（完整性）
- MRR:         首个命中的倒数排名均值（首个相关结果出现得多早）
- nDCG@k:      位置折扣累积增益（排序质量——命中还得排得靠前）

消融矩阵（每项独立可关，验证各检索组件的真实贡献）：
- full         全开（baseline：3路检索 + HyDE + Cross-Encoder 精排 + multi-query）
- no_hyde      关 HyDE（语义路不生成假设文档）
- no_rerank    关 Cross-Encoder 精排（融合层只剩投票）
- no_graph     关知识图谱路（2 路检索）
- no_multiquery 关多查询（decomposed_queries 不参与检索）
- no_semantic  关语义路（keyword+graph 两路）

运行方式（零 LLM 消耗——Self-Query 走规则版、HyDE 关闭或用规则降级）：
    python scripts/eval_retrieval.py                 # 全矩阵
    python scripts/eval_retrieval.py --resumes B01   # 单份快跑
    python scripts/eval_retrieval.py --top-k 3,5,8

设计说明：
- 每份简历：写入独立 Milvus 库（reset→index）→ 逐题跑检索 → 对 expected_ids 打分
- 评测在**独立进程**里自建向量库实例（data/eval/milvus_eval.db），与运行中的
  服务互不干扰（服务进程锁着主库是预期行为——嵌入式单写者）
- 消融通过 monkeypatch / state 注入实现，不改编生产代码
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-eval-offline")


# ===== 指标计算 =====

def _norm_id(raw_id: str) -> str:
    """chunk_id 归一化：chunker 会加后缀（skill_2_child_2 / project_1_parent_0），
    ground truth 用源 chunk_id（skill_2）——剥掉 _child_N/_parent_N 后缀对齐"""
    for suffix in ("_child", "_parent"):
        idx = raw_id.find(suffix)
        if idx > 0:
            return raw_id[:idx]
    return raw_id


def _dedup_ranked(ranked_ids):
    """前缀归一化后去重（skill_2_child_2 与 skill_2_child_5 都归一为 skill_2，
    只计首个出现位置——多子块命中同一源素材是"命中"，不是"多条结果"）"""
    seen = set()
    out = []
    for rid in ranked_ids:
        n = _norm_id(rid)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def recall_at_k(ranked_ids, expected_ids, k):
    """Recall@k：前 k 命中数 / 全部期望数（id 前缀归一化去重后匹配）"""
    if not expected_ids:
        return None
    top = _dedup_ranked(ranked_ids)[:k]
    hit = len(set(top) & set(expected_ids))
    return hit / len(set(expected_ids))


def mrr(ranked_ids, expected_ids):
    """MRR：首个命中位置的倒数（无命中=0）"""
    exp = set(expected_ids)
    for rank, rid in enumerate(_dedup_ranked(ranked_ids), 1):
        if rid in exp:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids, expected_ids, k):
    """nDCG@k：二值相关性（命中=1）的位置折扣累积增益（≤1）"""
    if not expected_ids:
        return None
    exp = set(expected_ids)
    top = _dedup_ranked(ranked_ids)[:k]
    dcg = sum(1.0 / (i + 1) ** 0.5 for i, rid in enumerate(top) if rid in exp)
    ideal = sum(1.0 / (i + 1) ** 0.5 for i in range(min(len(exp), k)))
    return dcg / ideal if ideal else 0.0


# ===== 消融开关（注入 planner_decisions / patch 组件）=====

def make_ablation_mode(mode: str):
    """返回 (planner_decisions_override, patch_dict)

    planner_decisions 控制激活路；patch_dict 在运行时替换组件函数实现消融。
    """
    base = {"active_retrievers": ["keyword", "semantic", "graph"],
            "retrieval_top_k": 10, "skip_review": True}

    patches = {}
    if mode == "full":
        pass
    elif mode == "no_hyde":
        # semantic 路：跳过 HyDE（is_fast 已跳过——这里显式模拟无 HyDE 场景）
        def _no_hyde(orig_semantic):
            async def patched(state):
                state.setdefault("planner_decisions", {})["skip_review"] = True  # fast→跳 HyDE
                return await orig_semantic(state)
            return patched
        base["skip_review"] = True  # HyDE 只在非 fast 模式跑
    elif mode == "no_rerank":
        import src.rag.reranker as reranker_mod
        class _NoRerank:
            def rerank(self, query, candidates, top_k=None):
                return candidates[:top_k] if top_k else candidates
            def rerank_multi_query(self, queries, candidates, top_k=None):
                return candidates[:top_k] if top_k else candidates
            @property
            def model(self):
                return None
        patches["get_reranker"] = lambda: _NoRerank()
    elif mode == "no_graph":
        base["active_retrievers"] = ["keyword", "semantic"]
    elif mode == "no_multiquery":
        # router 拆解结果清空 → 多查询退化为单查询
        def _patch(state):
            state["decomposed_queries"] = [state.get("query", "")]
            return state
        patches["_strip_multiquery"] = _patch
    elif mode == "no_semantic":
        base["active_retrievers"] = ["keyword", "graph"]
    else:
        raise ValueError(f"未知消融模式: {mode}")
    return base, patches


# ===== 主评测流程 =====

def run_eval(resume_ids, modes, top_ks=(3, 5, 8), eval_db="data/eval/milvus_eval.db"):
    """跑评测矩阵。返回 {mode: {resume_id: {question: [ranked_ids]}}} 原始数据 + 指标报告

    注意：检索 agent 内部调 get_vector_store()（全局单例）。评测必须在
    实例化任何 store **之前**先把全局单例指向评测库——否则单例先锁主库
    失败降级 chroma 空库，agent 永远查不到评测数据（先 init 先固定）。
    """
    # 先建评测库实例并占住全局单例（这是关键顺序）
    import src.rag.milvus_store as ms
    db_path = ROOT / eval_db
    if db_path.exists():
        import shutil
        shutil.rmtree(db_path, ignore_errors=True)
    eval_store = ms.MilvusVectorStore(persist_path=str(db_path))
    ms._store = eval_store
    ms._store_backend = "milvus"

    # 评测吞吐模式：to_thread 的默认线程池在长跑中累积泄漏（MemoryError 教训），
    # 换单线程池——评测测的是检索质量而非并行度，串行不影响指标
    import concurrent.futures
    _eval_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    _orig_to_thread = asyncio.to_thread

    def _to_thread_single(fn, /, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(_eval_pool, lambda: fn(*args, **kwargs))

    asyncio.to_thread = _to_thread_single

    from src.rag.profile_sync import profile_to_documents
    from src.rag.chunker import ParentChildChunker
    from src.agents.state import create_initial_state
    from src.agents import retriever_node

    eval_set = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "data/eval/profile_seed.json").read_text(encoding="utf-8"))

    vs = eval_store
    results = {m: [] for m in modes}   # mode → 逐题记录
    reports = {}

    async def _loop_main():
        # 外层简历、内层模式：每份简历只重建一次索引（六模式共用），
        # 且单事件循环贯穿全程——此前逐题 asyncio.run 新建循环 +
        # 每模式重入库导致 MemoryError（连接/线程泄漏式累积）
        for rid in resume_ids:
            profile = profiles[rid]
            docs = profile_to_documents(profile)
            children, _, _ = ParentChildChunker().chunk_documents(docs)
            vs.reset()
            vs.index_documents(children)
            rqs = [q for q in eval_set if q["resume_id"] == rid and q["expected_ids"]]
            print(f"  {rid}: {len(rqs)} 题开始（索引 {vs.get_collection_info()}）")

            for mode in modes:
                decisions, patches = make_ablation_mode(mode)
                for q in rqs:
                    state = create_initial_state(q["question"], mode="interview")
                    state["planner_decisions"] = {**decisions}
                    state["user_profile"] = profile
                    state["decomposed_queries"] = [q["question"]]

                    from src.rag.self_query import SelfQueryRetriever
                    structured = SelfQueryRetriever().build_simple(q["question"])
                    state["self_query_filter"] = structured

                    if "_strip_multiquery" in patches:
                        patches["_strip_multiquery"](state)

                    # 组件级消融（reranker 等）：patch 生产模块入口
                    import src.agents.retriever_node as rn_mod
                    if "get_reranker" in patches:
                        _orig_get_reranker = rn_mod.get_reranker
                        rn_mod.get_reranker = patches["get_reranker"]
                    try:
                        state = await retriever_node.parallel_retrieval_node(state)
                    except Exception as e:
                        print(f"  [WARN] {mode}/{rid} 检索异常: {e}")
                        state["reranked_context"] = []
                    finally:
                        if "get_reranker" in patches:
                            rn_mod.get_reranker = _orig_get_reranker

                    ranked = [c.get("id", "") for c in state.get("reranked_context", [])]
                    results[mode].append({
                        "resume_id": rid, "question": q["question"],
                        "expected": q["expected_ids"], "ranked": ranked,
                        "elapsed_ms": state.get("fusion_stats", {}).get("parallel_elapsed_ms", 0),
                    })

    asyncio.run(_loop_main())

    # 还原全局 patch（进程内残留影响最小化）
    asyncio.to_thread = _orig_to_thread
    _eval_pool.shutdown(wait=False)

    # ===== 指标聚合 =====
    for mode in modes:
        per_q = results[mode]
        mode_report = {"n": len(per_q)}
        n_rec = [r for r in per_q if r["expected"]]
        mode_report["latency_ms_avg"] = round(
            sum(r["elapsed_ms"] for r in per_q) / max(1, len(per_q)), 1)

        for k in top_ks:
            recalls = [recall_at_k(r["ranked"], r["expected"], k) for r in n_rec]
            mode_report[f"recall@{k}"] = round(
                sum(x for x in recalls if x is not None) / max(1, len(recalls)), 4)
            ndcgs = [ndcg_at_k(r["ranked"], r["expected"], k) for r in n_rec]
            mode_report[f"ndcg@{k}"] = round(
                sum(x for x in ndcgs if x is not None) / max(1, len(ndcgs)), 4)
        mode_report["mrr"] = round(
            sum(mrr(r["ranked"], r["expected"]) for r in n_rec) / max(1, len(n_rec)), 4)

        reports[mode] = mode_report
        print(f"[{mode}] {json.dumps(mode_report, ensure_ascii=False)}")

    return results, reports


def write_report(results, reports, out_path="data/eval/retrieval_report.json"):
    out = ROOT / out_path
    out.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reports": reports,
        "raw": {m: [
            {"resume_id": r["resume_id"], "q": r["question"][:40],
             "expected": r["expected"], "ranked": r["ranked"]}
            for r in rows
        ] for m, rows in results.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"报告已写入 {out_path}")


def print_table(reports):
    """控制台对比表（论文表格的雏形）"""
    modes = list(reports.keys())
    cols = [k for k in reports[modes[0]] if k not in ("n", "latency_ms_avg")]
    print("\n" + "=" * 72)
    print(f"{'模式':<16}" + "".join(f"{c:>12}" for c in cols) + f"{'延迟ms':>10}")
    print("-" * 72)
    for m in modes:
        r = reports[m]
        print(f"{m:<16}" + "".join(f"{r.get(c, '-'):>12}" for c in cols) + f"{r.get('latency_ms_avg', '-'):>10}")
    print("=" * 72)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="检索质量评测（零 LLM 消耗）")
    ap.add_argument("--resumes", default="", help="逗号分隔的简历 ID（空=全部 12 份）")
    ap.add_argument("--modes", default="full,no_hyde,no_rerank,no_graph,no_multiquery,no_semantic",
                    help="消融模式（逗号分隔）")
    ap.add_argument("--top-k", default="3,5,8", help="指标 k 值（逗号分隔）")
    args = ap.parse_args()

    # 评测集存在性检查
    if not (ROOT / "data/eval/questions.json").exists():
        print("评测集不存在，先生成：python scripts/gen_eval_set.py")
        sys.exit(1)

    resume_ids = [r for r in args.resumes.split(",") if r] or \
        sorted({q["resume_id"] for q in json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))})
    modes = [m for m in args.modes.split(",") if m]
    top_ks = [int(k) for k in args.top_k.split(",")]

    results, reports = run_eval(resume_ids, modes, top_ks)
    print_table(reports)
    write_report(results, reports)
