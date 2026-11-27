# -*- coding: utf-8 -*-
"""诊断：对比全量流水线 / fast / 单Agent 的回答里数字与简历原文的对应关系"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT / "data/eval/generation_e2e_report.json", encoding="utf-8"))

for arm in ("pipeline", "pipeline_fast", "single"):
    if arm not in d:
        continue
    print("=" * 80)
    print("ARM:", arm, d[arm]["summary"])
    for row in d[arm]["detail"][:4]:
        rid = row["resume_id"]
        ans = row.get("answer", "")
        resume = (ROOT / "data/eval/resumes" / f"resume_{rid}.md").read_text(encoding="utf-8")
        nums = re.findall(r"\d+(?:\.\d+)?\s*(?:%|万|倍|ms|s|分钟)?", ans)
        nums = [n.strip() for n in nums if n.strip() and not re.match(r"^\d{1}$", n.strip())]
        ungrounded = [n for n in nums if n not in resume and re.sub(r"\D", "", n) not in re.sub(r"\D", "", resume)]
        print(f"\n  {rid} len={len(ans)} nums={len(nums)} ungrounded={len(ungrounded)} {ungrounded[:10]}")
        print("   答案前 160 字:", ans[:160].replace("\n", " "))
