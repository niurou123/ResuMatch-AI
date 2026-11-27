# -*- coding: utf-8 -*-
"""复合问题分解链路的效果评测 —— 方面覆盖率（aspect coverage）

评测设计
--------
同一个复合问题、同一份简历基准、同一套规则化打分，比较三组：
    decomp  启用分解链路（分解 → 子问题并行作答 → 整合）
    plain   关闭分解（把 graph.is_composite 打桩为 False，其余链路不变）
    single  单次 LLM 调用（简历全文直送，无检索无评审）

指标
----
- 方面覆盖率：问题被拆成若干"必答方面"，回答中出现该方面任一关键词即算覆盖。
  这是规则判定，不依赖模型自评，也不存在循环论证。
- STAR 完整率 / 数字可回溯率 / 平均字数 / 平均耗时

用法
----
    python scripts/eval_decomposition.py --n 5
    python scripts/eval_decomposition.py --mode decomp --resume B01
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from eval_generation import check_star, check_numbers        # noqa: E402
from eval_baseline import run_single, summarize              # noqa: E402
from eval_generation_e2e import setup_eval_store, bind_fixed_pool  # noqa: E402

# 复合问题集：每题给出"必答方面"，每方面给一组可接受关键词
CASES = [
    {
        "q": "请比较你在电商订单中台和数据同步管道两个项目中承担的角色差异，以及各自最大的技术挑战是什么。",
        "aspects": {
            "订单中台角色": ["后端负责人", "负责人"],
            "同步管道角色": ["核心开发", "核心"],
            "订单中台挑战": ["异步", "削峰", "幂等", "分布式事务"],
            "同步管道挑战": ["CDC", "断点续传", "同步"],
        },
    },
    {
        "q": "分别说明订单中台的性能优化手段和数据同步管道的可靠性设计，并说明两者在取舍上有什么不同。",
        "aspects": {
            "订单性能手段": ["削峰", "异步", "幂等", "缓存", "延迟"],
            "同步可靠性": ["断点续传", "CDC", "重试", "一致性"],
            "取舍差异": ["取舍", "权衡", "代价", "区别", "不同"],
        },
    },
    {
        "q": "你的技术栈里哪些用于构建后端服务、哪些用于支撑数据处理？它们各自解决了什么问题？",
        "aspects": {
            "后端服务技术": ["FastAPI", "Django", "Python"],
            "数据处理技术": ["Celery", "Kafka", "Redis", "SQLAlchemy"],
            "解决的问题": ["并发", "异步", "解耦", "吞吐", "延迟", "存储"],
        },
    },
    {
        "q": "同时讲讲你在订单中台做的性能优化，以及在数据同步管道里做的稳定性保障。",
        "aspects": {
            "性能优化": ["削峰", "异步", "延迟", "吞吐", "优化"],
            "稳定性保障": ["断点续传", "幂等", "重试", "一致性", "稳定性"],
        },
    },
    {
        "q": "对比订单中台与数据同步管道两个项目，哪一个技术复杂度更高？请结合各自的实现细节说明理由。",
        "aspects": {
            "复杂度判断": ["复杂度", "更高", "更难", "复杂"],
            "订单实现细节": ["幂等", "分布式事务", "削峰", "异步"],
            "同步实现细节": ["CDC", "断点续传", "多源", "异构"],
        },
    },
]


def aspect_coverage(answer: str, aspects: dict) -> dict:
    """规则判定方面覆盖率：每个方面命中任一关键词即算覆盖"""
    text = answer or ""
    hit, detail = 0, {}
    for name, kws in aspects.items():
        ok = any(k.lower() in text.lower() for k in kws)
        detail[name] = ok
        hit += 1 if ok else 0
    return {"covered": hit, "total": len(aspects),
            "rate": round(hit / len(aspects), 4) if aspects else 0.0,
            "detail": detail}


async def run_pipeline_arms(cases, profile, resume_text, vs, with_decomp_flags):
    """跑流水线两组：分解开启 / 关闭（通过打桩 is_composite 实现干净 A/B）"""
    import src.agents.graph as G
    from src.agents.graph import run_interview_workflow
    from src.rag.profile_sync import profile_to_documents
    from src.rag.chunker import ParentChildChunker

    docs = profile_to_documents(profile)
    children, _, _ = ParentChildChunker().chunk_documents(docs)
    vs.reset()
    vs.index_documents(children)

    orig = G.is_composite
    rows = {}
    for arm, enable in with_decomp_flags:
        G.is_composite = orig if enable else (lambda _q: False)
        rows[arm] = []
        for i, case in enumerate(cases):
            t0 = time.time()
            err, answer = "", ""
            rounds, n_sub = 0, 0
            try:
                state = await run_interview_workflow(
                    case["q"], session_id=f"dec-{arm}-{i}", user_profile=profile,
                )
                answer = state.get("final_answer") or state.get("draft_answer") or ""
                rounds = int(state.get("evidence_rounds") or 0)
                n_sub = len(state.get("sub_questions") or [])
            except Exception as ex:
                err = str(ex)[:160]
            ms = round((time.time() - t0) * 1000, 1)
            cov = aspect_coverage(answer, case["aspects"])
            rows[arm].append({
                "arm": arm, "question": case["q"][:40], "answer_len": len(answer),
                "elapsed_ms": ms, "error": err, "coverage": cov, "evidence_rounds": rounds, "n_sub_questions": n_sub,
                "star": check_star(answer), "numbers": check_numbers(answer, resume_text),
            })
            print(f"  [{arm:6s}] {i+1}/{len(cases)} 覆盖 {cov['covered']}/{cov['total']} "
                  f"len={len(answer)} {ms}ms {('ERR:'+err) if err else ''}")
    G.is_composite = orig
    return rows


def agg(rows):
    s = summarize(rows)
    cov = [r["coverage"]["rate"] for r in rows]
    s["aspect_coverage"] = round(sum(cov) / len(cov), 4) if cov else 0.0
    s["n_full_cover"] = sum(1 for r in rows
                            if r["coverage"]["covered"] == r["coverage"]["total"])
    rs = [r.get("evidence_rounds") or 0 for r in rows]
    s["avg_evidence_rounds"] = round(sum(rs) / len(rs), 2) if rs else 0.0
    s["n_supplement_triggered"] = sum(1 for x in rs if x >= 2)
    return s


def main():
    ap = argparse.ArgumentParser(description="复合问题分解链路效果评测")
    ap.add_argument("--n", type=int, default=5, help="使用的复合问题数（最多 5）")
    ap.add_argument("--resume", default="B01")
    ap.add_argument("--mode", choices=["both", "decomp", "single"], default="both")
    ap.add_argument("--json", default="data/eval/decomposition_report.json")
    args = ap.parse_args()

    cases = CASES[:args.n]
    profiles = json.loads((ROOT / "data/eval/profile_seed.json").read_text(encoding="utf-8"))
    profile = profiles[args.resume]
    resume_text = (ROOT / "data/eval/resumes" / f"resume_{args.resume}.md").read_text(encoding="utf-8")

    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "resume": args.resume, "n_questions": len(cases),
              "model": os.environ.get("DEEPSEEK_MODEL", "")}

    if args.mode in ("both", "decomp"):
        print(f"=== 流水线：分解开启 vs 关闭（{len(cases)} 题）===")
        vs = setup_eval_store()
        pool = bind_fixed_pool()
        flags = [("decomp", True), ("plain", False)] if args.mode == "both" else [("decomp", True)]
        rows = asyncio.run(run_pipeline_arms(cases, profile, resume_text, vs, flags))
        for k, v in rows.items():
            report[k] = {"summary": agg(v), "detail": v}
        pool.shutdown(wait=False)

    if args.mode in ("both", "single"):
        print(f"\n=== 单次调用基线（{len(cases)} 题）===")
        qs = [{"resume_id": args.resume, "question": c["q"], "qtype": "composite"} for c in cases]
        rows = asyncio.run(run_single(qs, ROOT / "data/eval/resumes", len(qs)))
        for i, r in enumerate(rows):
            r["coverage"] = aspect_coverage(r.get("answer", ""), cases[i]["aspects"])
        report["single"] = {"summary": agg(rows), "detail": rows}

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    cols = [k for k in ("decomp", "plain", "single") if k in report]
    print("\n===== 对比（同一批复合问题、同一份简历基准）=====")
    head = f"{'指标':<20s}" + "".join(f"{c:>14s}" for c in cols)
    print(head)
    print("-" * len(head))
    rowsdef = [
        ("aspect_coverage", "方面覆盖率", True),
        ("n_full_cover", "全部方面命中题数", False),
        ("star_complete_rate", "STAR 完整率", True),
        ("avg_answer_len", "平均字数", False),
        ("avg_elapsed_ms", "平均耗时(ms)", False),
    ]
    for key, title, is_pct in rowsdef:
        line = f"{title:<20s}"
        for c in cols:
            v = report[c]["summary"].get(key)
            if v is None:
                cell = "—"
            elif is_pct:
                cell = f"{v * 100:.1f}%"
            elif isinstance(v, float):
                cell = f"{v:.1f}"
            else:
                cell = str(v)
            line += f"{cell:>14s}"
        print(line)
    print(f"\n模型: {report['model']}  |  报告: {out}")


if __name__ == "__main__":
    main()
