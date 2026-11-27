# -*- coding: utf-8 -*-
"""端到端生成质量评测 — 独立评测画像 + 独立向量库（基准一致）

为什么需要这个脚本（BUG_LOG 案例 29）：
    eval_generation.py 只向运行中的服务发问题，服务端用 data/profile.json（作者本人简历）
    作答，但比对基准是合成评测简历——两者不是同一份简历，其"数字可回溯率"无效。
    本脚本按 eval_retrieval.py 的方式，在**独立进程内**把评测简历装进独立 Milvus 库，
    并把评测画像直接注入工作流，使生成与比对基准严格一致。

三组对照（同一批题目、同一份简历基准）：
    pipeline       5 节点 LangGraph 工作流（规划→路由→三路并行检索+融合→STAR写作→三路评审+表决）
    pipeline_fast  同一工作流 + fast=True（跳过多轮评审回环，适合实时场景）
    single         单次 LLM 调用（简历全文直送，无检索、无评审、无回环）

指标（规则化检测，不依赖模型自评）：
    STAR 完整率 / 数字可回溯率 / 平均字数 / 平均耗时 / （流水线）平均评审分

用法：
    python scripts/eval_generation_e2e.py --n 6 --mode all        # 三方对比
    python scripts/eval_generation_e2e.py --n 6 --mode both       # 流水线 vs 单Agent
    python scripts/eval_generation_e2e.py --n 4 --mode fast       # 只跑 fast 模式

输出：data/eval/generation_e2e_report.json
"""
import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# 读取 .env（不覆盖已有环境变量）
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from eval_generation import check_star, check_numbers  # noqa: E402
from eval_baseline import run_single, summarize        # noqa: E402

ARM_LABEL = {
    "pipeline": "流水线(全量)",
    "pipeline_fast": "流水线(fast)",
    "single": "单Agent",
}


def setup_eval_store(eval_db="data/eval/milvus_eval.db"):
    """把全局向量库单例指向独立评测库（必须在任何 store 实例化之前）"""
    import src.rag.milvus_store as ms
    db_path = ROOT / eval_db
    if db_path.exists():
        import shutil
        shutil.rmtree(db_path, ignore_errors=True)
    eval_store = ms.MilvusVectorStore(persist_path=str(db_path))
    ms._store = eval_store
    ms._store_backend = "milvus"
    return eval_store


def bind_fixed_pool(workers=4):
    """长跑时 asyncio.to_thread 默认池会累积泄漏，改成固定小线程池"""
    import concurrent.futures
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    def _to_thread(fn, /, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(pool, lambda: fn(*args, **kwargs))

    asyncio.to_thread = _to_thread
    return pool


async def run_pipeline_arms(sample, profiles, vs, arms):
    """流水线各档位：每份简历只建一次索引，同题依次跑全量/fast，避免重复建索引

    arms: [(key, fast_bool), ...]
    """
    from src.rag.profile_sync import profile_to_documents
    from src.rag.chunker import ParentChildChunker
    from src.agents.graph import run_interview_workflow

    rows = {k: [] for k, _ in arms}
    by_resume = {}
    for q in sample:
        by_resume.setdefault(q["resume_id"], []).append(q)

    for rid, qs in by_resume.items():
        docs = profile_to_documents(profiles[rid])
        children, _, _ = ParentChildChunker().chunk_documents(docs)
        vs.reset()
        vs.index_documents(children)
        resume_text = (ROOT / "data/eval/resumes" / f"resume_{rid}.md").read_text(encoding="utf-8")
        print(f"  [{rid}] 索引完成（{vs.get_collection_info()}），{len(qs)} 题")

        for q in qs:
            for key, fast in arms:
                t0 = time.time()
                err, answer, review_total = "", "", None
                try:
                    state = await run_interview_workflow(
                        q["question"],
                        session_id=f"e2e-{key}-{rid}-{abs(hash(q['question'])) % 100000}",
                        user_profile=profiles[rid],
                        fast=fast,
                    )
                    answer = state.get("final_answer") or state.get("draft_answer") or ""
                    review_total = state.get("review_total")
                except Exception as ex:
                    err = str(ex)[:200]
                elapsed = round((time.time() - t0) * 1000, 1)
                star = check_star(answer)
                nums = check_numbers(answer, resume_text)
                rows[key].append({
                    "resume_id": rid, "question": q["question"][:50],
                    "qtype": q.get("qtype", ""),
                    "answer_len": len(answer), "elapsed_ms": elapsed, "error": err,
                    "star": star, "numbers": nums, "review_total": review_total,
                    "answer": answer,
                })
                mark = "✓" if star["complete"] else "✗"
                print(f"    {key:<14s} {rid} STAR={mark} len={len(answer)} {elapsed}ms"
                      f"{('  ERR:' + err) if err else ''}")
    return rows


def main():
    ap = argparse.ArgumentParser(description="端到端生成质量评测（流水线/快速/单Agent）")
    ap.add_argument("--n", type=int, default=6, help="评测题数")
    ap.add_argument("--mode", choices=["pipeline", "fast", "single", "both", "all"], default="all",
                    help="both=流水线+单Agent；all=全量+fast+单Agent")
    ap.add_argument("--resumes", nargs="*", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--json", default="data/eval/generation_e2e_report.json")
    args = ap.parse_args()

    questions = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "data/eval/profile_seed.json").read_text(encoding="utf-8"))
    resumes_dir = ROOT / "data/eval/resumes"

    pool = [q for q in questions
            if q.get("qtype") in ("technical_depth", "project_followup")
            and (not args.resumes or q["resume_id"] in args.resumes)]
    if not pool:
        print("没有可用题目")
        return
    rnd = random.Random(args.seed)
    sample = rnd.sample(pool, min(args.n, len(pool)))

    want_pipe = args.mode in ("pipeline", "both", "all")
    want_fast = args.mode in ("fast", "all")
    want_single = args.mode in ("single", "both", "all")

    arms = []
    if want_pipe:
        arms.append(("pipeline", False))
    if want_fast:
        arms.append(("pipeline_fast", True))

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n": len(sample), "seed": args.seed, "resumes": args.resumes,
        "model": os.environ.get("DEEPSEEK_MODEL", ""),
        "note": "独立评测画像+独立向量库，生成与比对基准一致（修正 BUG_LOG 案例 29）",
    }

    if arms:
        print(f"=== 流水线档位：{', '.join(k for k, _ in arms)}（{len(sample)} 题）===")
        vs = setup_eval_store()
        pool_exec = bind_fixed_pool()
        rows = asyncio.run(run_pipeline_arms(sample, profiles, vs, arms))
        for k, _ in arms:
            report[k] = {"summary": summarize(rows[k]), "detail": rows[k]}
        pool_exec.shutdown(wait=False)

    if want_single:
        print(f"\n=== 单Agent基线（{len(sample)} 题，一次调用/题）===")
        rows = asyncio.run(run_single(sample, resumes_dir, len(sample)))
        report["single"] = {"summary": summarize(rows), "detail": rows}

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    cols = [k for k in ("pipeline", "pipeline_fast", "single") if k in report]
    print("\n===== 对比（同一批题目、同一份简历基准）=====")
    head = f"{'指标':<18s}" + "".join(f"{ARM_LABEL[k]:>16s}" for k in cols)
    print(head)
    print("-" * len(head))

    def fmt(v, pct):
        if v is None:
            return "—"
        return f"{v:.2%}" if pct else f"{v}"

    for key, label, pct in [
        ("star_complete_rate", "STAR 完整率", True),
        ("number_grounded_rate", "数字可回溯率", True),
        ("avg_answer_len", "平均字数", False),
        ("avg_elapsed_ms", "平均耗时(ms)", False),
    ]:
        line = f"{label:<18s}"
        for k in cols:
            line += f"{fmt(report[k]['summary'].get(key), pct):>16s}"
        print(line)

    print(f"\n模型: {report['model']}  |  报告: {out}")


if __name__ == "__main__":
    main()
