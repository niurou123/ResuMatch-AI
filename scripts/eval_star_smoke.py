# -*- coding: utf-8 -*-
"""STAR 结构单题抽查 — 改完 writer prompt 后快速回归（1 次 LLM 调用）

用途：直接调用 build_star_prompt + DeepSeekClient，不经过 HTTP 服务与检索链路，
1 次调用即可看出「四段式标签是否出现、STAR 是否完整、数字能否回溯原文」。

用法：
    python scripts/eval_star_smoke.py                 # 默认 B01 的第 1 道项目题
    python scripts/eval_star_smoke.py --resume B03
    python scripts/eval_star_smoke.py --question "讲讲你做的订单中台"
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# 读取项目 .env（不覆盖已有环境变量）
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from eval_generation import check_star, check_numbers  # noqa: E402
from src.core.prompts import build_star_prompt        # noqa: E402


async def run(resume_id: str, question: str = ""):
    from src.core.llm_client import DeepSeekClient, Message

    seeds = json.loads((ROOT / "data/eval/profile_seed.json").read_text(encoding="utf-8"))
    if resume_id not in seeds:
        raise SystemExit(f"未知简历 ID: {resume_id}")
    seed = seeds[resume_id]
    resume_text = (ROOT / "data/eval/resumes" / f"resume_{resume_id}.md").read_text(encoding="utf-8")

    if not question:
        qs = json.loads((ROOT / "data/eval/questions.json").read_text(encoding="utf-8"))
        pool = [q for q in qs if q["resume_id"] == resume_id
                and q.get("qtype") in ("technical_depth", "project_followup")]
        question = pool[0]["question"] if pool else "请介绍你最有代表性的项目"

    state = {
        "query": question,
        "reranked_context": [{
            "collection": "resume",
            "content": resume_text,
            "metadata": {"name": resume_id},
            "score": 1.0,
        }],
        "retrieved_projects": [],
        "user_profile": seed,
        "revision_feedback": "",
        "conversation_history": [],
    }
    system_prompt, user_prompt = build_star_prompt(state)

    client = DeepSeekClient()
    try:
        resp = await client.chat(
            [Message(role="system", content=system_prompt),
             Message(role="user", content=user_prompt)],
            temperature=0.3,
        )
    finally:
        try:
            await client.aclose()
        except Exception:
            pass

    answer = resp.content or ""
    star = check_star(answer)
    nums = check_numbers(answer, resume_text)

    print("=" * 70)
    print("简历:", resume_id, "| 问题:", question)
    print("-" * 70)
    print(answer)
    print("-" * 70)
    print(f"STAR 各要素: S={star['S']} T={star['T']} A={star['A']} R={star['R']} "
          f"→ 完整={star['complete']}")
    print(f"数字可回溯: {nums['n_grounded']}/{nums['n_numbers']} "
          f"= {nums['rate'] if nums['rate'] is None else round(nums['rate'], 3)}")
    print(f"答案长度: {len(answer)} 字")
    return {"answer": answer, "star": star, "numbers": nums}


def main():
    ap = argparse.ArgumentParser(description="STAR 结构单题抽查（1 次 LLM 调用）")
    ap.add_argument("--resume", default="B01")
    ap.add_argument("--question", default="")
    args = ap.parse_args()
    asyncio.run(run(args.resume, args.question))


if __name__ == "__main__":
    main()
