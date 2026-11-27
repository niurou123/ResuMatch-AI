# -*- coding: utf-8 -*-
"""单 Agent 基线 vs 多 Agent 流水线 — 回答"多 Agent 是否必要"

对照组设计（同一批题目、同一套规则化指标、同一份简历原文）：
- single   ：一次 LLM 调用。直接把简历全文 + 问题交给模型，不做检索、不做评审、不做回环。
             （这是对基线"最有利"的设置——模型看到简历全文，不承担检索损失）
- pipeline ：调用运行中的服务 /interview/answer，即 5 节点 LangGraph 工作流
             （规划 → 路由 → 三路并行检索+融合 → STAR 写作 → 三路并行评审+多数表决）

指标（均为规则化检测，不依赖模型自评，见 eval_generation.py）：
- STAR 完整率        S/T/A/R 四要素是否齐备
- 量化数字可回溯率  回答中的数字能否在简历原文中找到
- 答案平均字数、平均耗时

用法：
    # 先启动后端服务，再执行
    python scripts/eval_baseline.py --n 10
    python scripts/eval_baseline.py --n 10 --api http://localhost:8000/api/v1
    python scripts/eval_baseline.py --mode single --n 5     # 只跑基线

输出：data/eval/baseline_report.json；若已存在 generation_report.json，
会自动读入并打印「流水线 vs 单Agent」对比表。
"""
import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from eval_generation import check_star, check_numbers  # noqa: E402

SINGLE_SYSTEM = (
    "你是一名求职面试辅导助手。请仅依据用户提供的简历内容回答问题，"
    "按 STAR 结构（情境 Situation、任务 Task、行动 Action、结果 Result）组织回答，"
    "回答中出现的所有数字必须来自简历原文，不得虚构或推断。"
)

SINGLE_USER = (
    "【简历全文】\n{resume}\n\n"
    "【面试问题】\n{question}\n\n"
    "请按 STAR 结构作答，控制在 400 字以内。"
)


async def run_single(questions, resumes_dir, n, temperature=0.3):
    """单 Agent 基线：一次调用，无检索、无评审、无回环"""
    from src.core.llm_client import DeepSeekClient, Message

    client = DeepSeekClient()
    rows = []
    try:
        for i, q in enumerate(questions, 1):
            rid = q["resume_id"]
            resume_text = (resumes_dir / f"resume_{rid}.md").read_text(encoding="utf-8")
            t0 = time.time()
            err = ""
            answer = ""
            try:
                resp = await client.chat(
                    [Message(role="system", content=SINGLE_SYSTEM),
                     Message(role="user", content=SINGLE_USER.format(
                         resume=resume_text, question=q["question"]))],
                    temperature=temperature,
                )
                answer = resp.content or ""
            except Exception as ex:
                err = str(ex)[:160]
            elapsed = round((time.time() - t0) * 1000, 1)
            rows.append({
                "resume_id": rid,
                "question": q["question"][:50],
                "qtype": q["qtype"],
                "answer_len": len(answer),
                "elapsed_ms": elapsed,
                "error": err,
                "star": check_star(answer),
                "numbers": check_numbers(answer, resume_text),
                "answer": answer,
            })
            flag = "✓" if rows[-1]["star"]["complete"] else "✗"
            print(f"[{i}/{len(questions)}] {rid} STAR={flag} "
                  f"len={len(answer)} {elapsed}ms {('ERR:' + err) if err else ''}")
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
    return rows


def run_pipeline(questions, api):
    """多 Agent 流水线：调用运行中的服务"""
    import httpx

    rows = []
    with httpx.Client(timeout=300) as client:
        for i, q in enumerate(questions, 1):
            rid = q["resume_id"]
            t0 = time.time()
            answer, err, review_total = "", "", None
            try:
                r = client.post(f"{api}/interview/answer", json={"question": q["question"]})
                d = r.json()
                answer = d.get("answer") or ""
                err = d.get("error") or ""
                review_total = d.get("review_total")
            except Exception as ex:
                err = str(ex)[:160]
            elapsed = round((time.time() - t0) * 1000, 1)
            rows.append({
                "resume_id": rid,
                "question": q["question"][:50],
                "qtype": q["qtype"],
                "answer_len": len(answer),
                "elapsed_ms": elapsed,
                "error": err,
                "star": check_star(answer),
                "numbers": check_numbers(answer, ""),   # 服务端已检索，无法直接拿到简历原文比对
                "review_total": review_total,
                "answer": answer,
            })
            print(f"[{i}/{len(questions)}] {rid} len={len(answer)} {elapsed}ms {('ERR:' + err) if err else ''}")
    return rows


def summarize(rows):
    ok = [r for r in rows if not r.get("error")]
    n = len(rows)
    star_rate = sum(1 for r in ok if r["star"]["complete"]) / len(ok) if ok else 0.0
    num_rows = [r for r in ok if r["numbers"]["rate"] is not None]
    num_rate = (sum(r["numbers"]["rate"] for r in num_rows) / len(num_rows)) if num_rows else None
    return {
        "n": n,
        "n_ok": len(ok),
        "star_complete_rate": round(star_rate, 4),
        "number_grounded_rate": round(num_rate, 4) if num_rate is not None else None,
        "avg_answer_len": round(sum(r["answer_len"] for r in ok) / len(ok), 1) if ok else 0,
        "avg_elapsed_ms": round(sum(r["elapsed_ms"] for r in ok) / len(ok), 1) if ok else 0,
    }


def main():
    ap = argparse.ArgumentParser(description="单Agent基线 vs 多Agent流水线对比")
    ap.add_argument("--n", type=int, default=10, help="评测题数")
    ap.add_argument("--mode", choices=["single", "pipeline", "both"], default="both")
    ap.add_argument("--api", default="http://localhost:8721/api/v1")
    ap.add_argument("--resumes", nargs="*", default=None)
    ap.add_argument("--seed", type=int, default=42, help="抽样随机种子（保证可复现）")
    ap.add_argument("--json", default="data/eval/baseline_report.json")
    args = ap.parse_args()

    questions = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
    resumes_dir = ROOT / "data/eval/resumes"
    pool = [q for q in questions
            if q.get("qtype") in ("technical_depth", "project_followup")
            and (not args.resumes or q["resume_id"] in args.resumes)]
    if not pool:
        print("没有可用题目")
        return
    rnd = random.Random(args.seed)
    sample = rnd.sample(pool, min(args.n, len(pool)))

    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "n": len(sample), "seed": args.seed, "resumes": args.resumes}

    if args.mode in ("single", "both"):
        print(f"=== 单Agent基线（{len(sample)} 题，一次调用/题）===")
        rows = asyncio.run(run_single(sample, resumes_dir, len(sample)))
        report["single"] = {"summary": summarize(rows), "detail": rows}

    if args.mode in ("pipeline", "both"):
        print(f"\n=== 多Agent流水线（{len(sample)} 题，服务 {args.api}）===")
        rows = run_pipeline(sample, args.api)
        report["pipeline"] = {"summary": summarize(rows), "detail": rows}

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 对比 =====")
    hdr = f"{'指标':<20s}{'单Agent':>12s}{'多Agent流水线':>16s}"
    print(hdr)
    print("-" * len(hdr))
    s = (report.get("single") or {}).get("summary")
    p = (report.get("pipeline") or {}).get("summary")
    for key, label, pct in [
        ("star_complete_rate", "STAR 完整率", True),
        ("number_grounded_rate", "数字可回溯率", True),
        ("avg_answer_len", "平均字数", False),
        ("avg_elapsed_ms", "平均耗时(ms)", False),
    ]:
        sv = s.get(key) if s else None
        pv = p.get(key) if p else None
        fmt = (lambda v: "—" if v is None else (f"{v:.2%}" if pct else f"{v}"))
        print(f"{label:<20s}{fmt(sv):>12s}{fmt(pv):>16s}")
    print(f"\n报告已写入 {out}")


if __name__ == "__main__":
    main()
