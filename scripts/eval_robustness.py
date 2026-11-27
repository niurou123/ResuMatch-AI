# -*- coding: utf-8 -*-
"""解析鲁棒性评测 —— 合成评测集 vs 外部真实语料

背景：字段准确率实验用的是程序化生成的规范排版简历（Markdown/纯文本结构规整），
指标只能代表"对规范文本的保真度"。真实简历来自不同模板、含多栏、表格、PDF 等，
解析难度显著上升。本脚本在同一套解析器上分别跑两组语料，量化泛化差距：

  synthetic  12 份程序化生成简历（data/eval/resumes/*.md）
  external   48 份公开语料（data/eval/resumes_ext/，CC0 / MIT，含 8 份 PDF）

指标（不依赖人工标注，衡量"解析器在真实文本上能抽出多少结构"）：
  解析成功率     未抛异常且抽到至少一个字段
  分区识别数     识别出的分区个数（教育/技能/项目/成果/工作）
  字段产出       技能、项目、教育、成果的平均抽取条数
  有项目比例     抽到 ≥1 个项目的简历占比
  平均耗时       单份解析耗时

用法：
    python scripts/eval_robustness.py
    python scripts/eval_robustness.py --json data/eval/robustness_report.json
"""
import argparse
import json
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-eval-offline")

from src.rag.parser import ResumeParser  # noqa: E402

EXT_DIR = ROOT / "data" / "eval" / "resumes_ext"
SYN_DIR = ROOT / "data" / "eval" / "resumes"


def basic_name(p: Path) -> str:
    return p.name


def run_group(parser: ResumeParser, files, group: str):
    rows = []
    for fp in files:
        t0 = time.time()
        err, res = "", None
        try:
            res = parser.parse(str(fp))
        except Exception as ex:
            err = f"{type(ex).__name__}: {str(ex)[:100]}"
        ms = round((time.time() - t0) * 1000, 1)

        n_sections = len(res.sections or {}) if res else 0
        n_skills = len(res.skills or []) if res else 0
        n_proj = len(res.projects or []) if res else 0
        n_edu = len(res.education or []) if res else 0
        n_ach = len(res.achievements or []) if res else 0
        n_fields = n_skills + n_proj + n_edu + n_ach
        raw_len = len((res.raw_text or "").strip()) if res else 0
        ok = (not err) and n_fields > 0

        rows.append({
            "group": group, "file": fp.name, "ok": ok, "error": err,
            "n_sections": n_sections, "n_skills": n_skills, "n_projects": n_proj,
            "n_education": n_edu, "n_achievements": n_ach, "n_fields": n_fields,
            "raw_chars": raw_len,
            "elapsed_ms": ms,
        })
        flag = "✓" if ok else ("✗" if not err else "✗ERR")
        print(f"  [{group:9s}] {flag} {fp.name:22s} 分区{n_sections} 技能{n_skills:2d} "
              f"项目{n_proj} 教育{n_edu} 成果{n_ach}  {ms:.0f}ms {err[:50]}")
    return rows


def summarize(rows):
    if not rows:
        return {}
    ok = [r for r in rows if r["ok"]]
    def mean(key, src=None):
        src = src if src is not None else rows
        return round(sum(r[key] for r in src) / len(src), 2) if src else 0.0
    return {
        "n": len(rows),
        "success_rate": round(len(ok) / len(rows), 4),
        "n_success": len(ok),
        "n_error": sum(1 for r in rows if r["error"]),
        "avg_sections": mean("n_sections"),
        "avg_skills": mean("n_skills"),
        "avg_projects": mean("n_projects"),
        "avg_education": mean("n_education"),
        "avg_achievements": mean("n_achievements"),
        "avg_fields": mean("n_fields"),
        "with_projects_rate": round(sum(1 for r in rows if r["n_projects"] > 0) / len(rows), 4),
        "with_education_rate": round(sum(1 for r in rows if r["n_education"] > 0) / len(rows), 4),
        "median_elapsed_ms": round(st.median([r["elapsed_ms"] for r in rows]), 1),
        "text_extract_rate": round(sum(1 for r in rows if r["raw_chars"] >= 200) / len(rows), 4),
        "avg_raw_chars": round(sum(r["raw_chars"] for r in rows) / len(rows), 1),
    }


def main():
    ap = argparse.ArgumentParser(description="解析鲁棒性评测（合成 vs 外部语料）")
    ap.add_argument("--json", default="data/eval/robustness_report.json")
    args = ap.parse_args()

    parser = ResumeParser()
    syn_files = sorted(SYN_DIR.glob("*.md"))
    ext_files = sorted([p for p in EXT_DIR.iterdir()
                        if p.suffix.lower() in (".txt", ".pdf", ".md", ".docx")])

    print(f"=== 合成语料（{len(syn_files)} 份，程序化生成）===")
    syn_rows = run_group(parser, syn_files, "synthetic")
    print(f"\n=== 外部语料（{len(ext_files)} 份，公开数据集 CC0 / MIT）===")
    ext_rows = run_group(parser, ext_files, "external")

    syn_s, ext_s = summarize(syn_rows), summarize(ext_rows)
    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "synthetic": {"summary": syn_s, "detail": syn_rows},
              "external": {"summary": ext_s, "detail": ext_rows}}

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 对比（同一解析器、不同语料）=====")
    head = f"{'指标':<18s}{'合成语料':>12s}{'外部语料':>12s}"
    print(head)
    print("-" * len(head))
    items = [
        ("n", "样本数"), ("text_extract_rate", "文本提取成功率"),
        ("success_rate", "结构化成功率"), ("n_error", "异常数"),
        ("avg_raw_chars", "平均文本字符"),
        ("avg_sections", "平均分区数"), ("avg_skills", "平均技能数"),
        ("avg_projects", "平均项目数"), ("avg_education", "平均教育条数"),
        ("avg_achievements", "平均成果数"), ("avg_fields", "平均字段总数"),
        ("with_projects_rate", "含项目比例"), ("with_education_rate", "含教育比例"),
        ("median_elapsed_ms", "耗时中位(ms)"),
    ]
    for key, title in items:
        sv, ev = syn_s.get(key, "—"), ext_s.get(key, "—")
        if isinstance(sv, float) and key.endswith("rate"):
            sv, ev = f"{sv * 100:.1f}%", f"{ev * 100:.1f}%"
        print(f"{title:<18s}{str(sv):>12s}{str(ev):>12s}")

    # 失败清单
    fails = [r for r in ext_rows if not r["ok"]]
    if fails:
        print(f"\n外部语料未成功解析 {len(fails)} 份：")
        for r in fails[:12]:
            print(f"  - {r['file']}: {r['error'][:80] or '未抽到任何字段'}")

    print(f"\n报告已写入 {out}")


if __name__ == "__main__":
    main()
