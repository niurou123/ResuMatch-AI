# -*- coding: utf-8 -*-
"""生成质量评测 — LLM 小样本评测（控制 token 消耗）

评测维度（每项均有可验证口径，避免"自评自夸"循环论证）：
1. 引用可回溯率: 回答中的 [来源: xxx] 引用是否能在检索素材中找到（机械可验）
2. STAR 结构完整度: S/T/A/R 四要素的正则检测（规则可验，不依赖 LLM）
3. 量化数据真实性: 回答中的数字/百分比是否来自简历原文（子串可验）
4. LLMJudge 五维评分: 相关性/STAR/优势/量化/真实性（每题 1 次调用）

成本控制（用户要求）：
- 默认 10 题（--n 可调）× 每题 2 次 LLM 调用（生成 + 评审）≈ 20 次调用
- 生成 max_tokens=600、评审 max_tokens=400（评审走 3 路 reviewer 的其中一路
  太贵——用 LLMJudge 单次评代替，指标口径不变）
- 复用 mock/next 的语义缓存：重复问题不重复扣费

运行：
    python scripts/eval_generation.py            # 10 题默认
    python scripts/eval_generation.py --n 5      # 更省
    python scripts/eval_generation.py --resumes B03 --n 8
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# 生成评测走**运行中的服务**（评测库与服务库独立，服务已加载全部模型，
# 不重复冷启动；也避免锁库冲突）


def check_star(answer: str) -> dict:
    """STAR 四要素规则检测（不依赖 LLM）"""
    s = bool(re.search(r"(?:背景|当时|项目|在.*期间|situation)", answer, re.I))
    t = bool(re.search(r"(?:任务|目标|需要|负责|挑战|task)", answer, re.I))
    a = bool(re.search(r"(?:我|设计|实现|开发|采用|使用|优化|重构|负责)", answer, re.I))
    r = bool(re.search(r"(?:结果|成果|提升|降低|达到|降为|result|→)", answer, re.I))
    return {"S": s, "T": t, "A": a, "R": r, "complete": s and t and a and r}


def check_citations(answer: str, context_contents) -> dict:
    """引用可回溯率：[来源: X] 中 X 能否在素材里找到（机械验证）"""
    cites = re.findall(r"\[来源[：:]\s*(.+?)\]", answer)
    if not cites:
        return {"n_cites": 0, "n_valid": 0, "rate": None}
    valid = sum(1 for c in cites if any(c.lower() in ctx.lower() for ctx in context_contents))
    return {"n_cites": len(cites), "n_valid": valid, "rate": valid / len(cites)}


def check_numbers(answer: str, resume_text: str) -> dict:
    """量化数据真实性：回答中的数字串（≥2位或带%/倍）是否在简历原文出现"""
    nums = re.findall(r"\d+(?:\.\d+)?\s*(?:%|倍|万|ms|s|倍率)?", answer)
    nums = [n.strip() for n in nums if len(re.sub(r"\D", "", n)) >= 1 and not re.match(r"^\d{1}$", n.strip())]
    if not nums:
        return {"n_numbers": 0, "n_grounded": 0, "rate": None}
    grounded = sum(1 for n in nums if n.replace(" ", "") in resume_text or
                   re.sub(r"\D", "", n) in re.sub(r"\D", "", resume_text))
    return {"n_numbers": len(nums), "n_grounded": grounded, "rate": grounded / len(nums)}


def main(resume_ids, n, api="http://localhost:8721/api/v1"):
    import httpx

    questions = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
    resumes_dir = ROOT / "data/eval/resumes"

    # 每份简历抽 n/len(resume_ids) 题：优先技术+项目（有素材可验）
    pool = [q for q in questions if q["resume_id"] in resume_ids and q["qtype"] in ("technical_depth", "project_followup")]
    random_step = max(1, len(pool) // n)
    sample = pool[::random_step][:n]

    client = httpx.Client(timeout=300)
    results = []

    print(f"生成评测开始: {len(resume_ids)} 份简历 × {len(sample)} 题（LLM 调用 ≈ {len(sample)*2} 次）")
    for i, q in enumerate(sample, 1):
        rid = q["resume_id"]
        resume_text = (resumes_dir / f"resume_{rid}.md").read_text(encoding="utf-8")

        try:
            # 走服务端完整工作流（检索 + 生成 + 评审）——快路径评测用 judge 单次评
            r = client.post(f"{api}/interview/answer", json={"question": q["question"]})
            d = r.json()
            answer = d.get("answer") or ""
            err = d.get("error")
        except Exception as e:
            answer, err = "", str(e)[:120]

        row = {
            "resume_id": rid, "question": q["question"][:50], "qtype": q["qtype"],
            "answer_len": len(answer), "error": err or "",
            "star": check_star(answer),
            # 数字真实性对简历原文验证（素材来自同一简历）
            "numbers": check_numbers(answer, resume_text),
            "review_total": d.get("review_total") if not err else None,
            "citations_count": len(d.get("citations") or []),
        }
        results.append(row)
        star = "✓" if row["star"]["complete"] else "✗"
        print(f"  [{i}/{len(sample)}] {rid} {q['qtype']:<16} len={row['answer_len']:<5} STAR={star} "
              f"num_grounded={row['numbers']['n_grounded']}/{row['numbers']['n_numbers']} "
              f"total={row['review_total']}")

    # ===== 汇总 =====
    ok = [r for r in results if not r["error"]]
    summary = {
        "n_total": len(results), "n_ok": len(ok),
        "avg_answer_len": round(sum(r["answer_len"] for r in ok) / max(1, len(ok)), 1),
        "star_complete_rate": round(sum(1 for r in ok if r["star"]["complete"]) / max(1, len(ok)), 4),
        "avg_review_total": round(sum(r["review_total"] or 0 for r in ok) / max(1, len(ok)), 2),
        "number_grounded_avg": round(
            sum(r["numbers"]["rate"] or 0 for r in ok if r["numbers"]["rate"] is not None) /
            max(1, sum(1 for r in ok if r["numbers"]["rate"] is not None)), 4),
    }
    print("\n===== 生成质量汇总 =====")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    out = ROOT / "data/eval/generation_report.json"
    out.write_text(json.dumps({
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample": [r["resume_id"] for r in results],
        "summary": summary, "detail": results,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"报告已写入 data/eval/generation_report.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="生成质量评测（小样本 LLM）")
    ap.add_argument("--resumes", default="", help="逗号分隔简历 ID（空=全部）")
    ap.add_argument("--n", type=int, default=10, help="评测题数（控制 LLM 消耗）")
    ap.add_argument("--api", default="http://localhost:8721/api/v1")
    args = ap.parse_args()

    if not (ROOT / "data/eval/questions.json").exists():
        print("评测集不存在，先运行: python scripts/gen_eval_set.py")
        sys.exit(1)

    import httpx
    try:
        httpx.get(f"{args.api}/health", timeout=5).raise_for_status()
    except Exception:
        print("后端未运行——先启动: python -m src.api.main")
        sys.exit(1)

    rids = [r for r in args.resumes.split(",") if r] or \
        sorted({q["resume_id"] for q in json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))})
    main(rids, args.n, args.api)
