# -*- coding: utf-8 -*-
"""字段提取准确率评测 — 零 LLM 消耗，可复现

对照 data/eval/profile_seed.json 中的标注真值（生成评测集时的种子数据），
评估 ResumeParser 的字段级提取质量。本脚本补充 eval_retrieval.py 与
eval_generation.py 未覆盖的环节：简历解析保真度。

指标定义：
- 技能     集合级 Precision / Recall / F1（归一化后比对）
- 项目     项目名命中率、角色命中率、技术栈集合 F1、关键成果命中率、项目数一致率
- 教育     学校 / 学历 / 专业 三项命中率
- 成果     描述相似度命中率（字符 2-gram Jaccard ≥ 0.5 记为命中）
- 总字段准确率 = 上述可判定字段正确数之和 / 应判定字段数之和

运行：
    python scripts/eval_extraction.py
    python scripts/eval_extraction.py --resumes B01 B02
    python scripts/eval_extraction.py --json data/eval/extraction_report.json

说明：评测集简历为程序化生成的干净文本（非扫描件），因此本指标衡量的是
"解析规则对规范排版的保真度"，不代表复杂真实简历（含图表、双栏、扫描）的表现。
"""
import argparse
import json
import re
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-eval-offline")

from src.rag.parser import ResumeParser  # noqa: E402

PUNCT = set(string.punctuation) | set("，。、；：（）【】《》“”‘’·—…　")


def norm(text: str) -> str:
    """归一化：小写、去标点与空白、去零宽字符"""
    if not text:
        return ""
    s = str(text).lower()
    s = s.replace("\u200b", "").replace("\ufeff", "")
    s = "".join(ch for ch in s if ch not in PUNCT and not ch.isspace())
    return s


def bigram_jaccard(a: str, b: str) -> float:
    """字符 2-gram Jaccard 相似度"""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    ga = {na[i:i + 2] for i in range(len(na) - 1)} or {na}
    gb = {nb[i:i + 2] for i in range(len(nb) - 1)} or {nb}
    inter = len(ga & gb)
    union = len(ga | gb)
    return inter / union if union else 0.0


def contains_either(a: str, b: str) -> bool:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    return na in nb or nb in na


def set_prf(pred: set, gold: set):
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "pred": len(pred), "gold": len(gold),
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def eval_one(resume_id: str, seed: dict, parsed) -> dict:
    """单份简历的字段级比对"""
    detail = {"id": resume_id,
              "parsed_counts": {
                  "skills": len(parsed.skills or []),
                  "projects": len(parsed.projects or []),
                  "education": len(parsed.education or []),
                  "achievements": len(parsed.achievements or []),
              },
              "gold_counts": {
                  "skills": len(seed.get("skills") or []),
                  "projects": len(seed.get("projects") or []),
                  "education": len(seed.get("education") or []),
                  "achievements": len(seed.get("achievements") or []),
              }}

    # ---------- 技能 ----------
    gold_skills = {norm(s.get("name")) for s in (seed.get("skills") or []) if s.get("name")}
    pred_skills = {norm(s.get("name")) for s in (parsed.skills or []) if s.get("name")}
    detail["skills"] = set_prf(pred_skills, gold_skills)

    # ---------- 项目 ----------
    gold_projs = seed.get("projects") or []
    pred_projs = parsed.projects or []
    name_hit = role_hit = result_hit = 0
    tech_micro = {"tp": 0, "pred": 0, "gold": 0}
    used = set()
    for gp in gold_projs:
        gname = gp.get("name", "")
        match_idx = None
        for i, pp in enumerate(pred_projs):
            if i in used:
                continue
            if contains_either(gname, pp.get("name", "")):
                match_idx = i
                break
        if match_idx is None:
            continue
        used.add(match_idx)
        pp = pred_projs[match_idx]
        name_hit += 1
        if contains_either(gp.get("role", ""), pp.get("role", "")):
            role_hit += 1
        gt = {norm(t) for t in (gp.get("tech_stack") or []) if t}
        pt = {norm(t) for t in (pp.get("tech_stack") or []) if t}
        tech_micro["tp"] += len(gt & pt)
        tech_micro["pred"] += len(pt)
        tech_micro["gold"] += len(gt)
        gres = gp.get("key_result", "") or gp.get("description", "")
        pres = (pp.get("key_result", "") or "") + " " + (pp.get("description", "") or "")
        if bigram_jaccard(gres, pres) >= 0.5 or contains_either(gres, pres):
            result_hit += 1

    n_gold_p = len(gold_projs)
    detail["projects"] = {
        "gold": n_gold_p,
        "pred": len(pred_projs),
        "count_exact_match": int(len(pred_projs) == n_gold_p),
        "name_hit": name_hit,
        "role_hit": role_hit,
        "result_hit": result_hit,
        "name_rate": round(name_hit / n_gold_p, 4) if n_gold_p else 0.0,
        "role_rate": round(role_hit / n_gold_p, 4) if n_gold_p else 0.0,
        "result_rate": round(result_hit / n_gold_p, 4) if n_gold_p else 0.0,
        "tech_f1": set_prf(set(), set())["f1"] if not tech_micro["gold"] else round(
            2 * tech_micro["tp"] / (tech_micro["pred"] + tech_micro["gold"]), 4),
    }

    # ---------- 教育 ----------
    gold_edu = seed.get("education") or []
    pred_edu = parsed.education or []
    school_hit = degree_hit = major_hit = 0
    used_e = set()
    for ge in gold_edu:
        idx = None
        for i, pe in enumerate(pred_edu):
            if i in used_e:
                continue
            if contains_either(ge.get("school", ""), pe.get("school", "")):
                idx = i
                break
        if idx is None:
            continue
        used_e.add(idx)
        pe = pred_edu[idx]
        school_hit += 1
        if contains_either(ge.get("degree", ""), pe.get("degree", "")):
            degree_hit += 1
        if contains_either(ge.get("major", ""), pe.get("major", "")):
            major_hit += 1
    n_gold_e = len(gold_edu)
    detail["education"] = {
        "gold": n_gold_e, "pred": len(pred_edu),
        "school_hit": school_hit, "degree_hit": degree_hit, "major_hit": major_hit,
        "school_rate": round(school_hit / n_gold_e, 4) if n_gold_e else 0.0,
        "degree_rate": round(degree_hit / n_gold_e, 4) if n_gold_e else 0.0,
        "major_rate": round(major_hit / n_gold_e, 4) if n_gold_e else 0.0,
    }

    # ---------- 成果 ----------
    gold_ach = [a.get("description", "") for a in (seed.get("achievements") or []) if a.get("description")]
    pred_ach = [a.get("description", "") for a in (parsed.achievements or []) if a.get("description")]
    ach_hit = 0
    for ga in gold_ach:
        best = max((bigram_jaccard(ga, pa) for pa in pred_ach), default=0.0)
        if best >= 0.5 or any(contains_either(ga, pa) for pa in pred_ach):
            ach_hit += 1
    n_gold_a = len(gold_ach)
    detail["achievements"] = {
        "gold": n_gold_a, "pred": len(pred_ach), "hit": ach_hit,
        "rate": round(ach_hit / n_gold_a, 4) if n_gold_a else 0.0,
    }

    # ---------- 总字段准确率 ----------
    correct = (detail["skills"]["tp"]
               + name_hit + role_hit + result_hit + tech_micro["tp"]
               + school_hit + degree_hit + major_hit
               + ach_hit)
    total = (len(gold_skills)
             + n_gold_p * 3 + tech_micro["gold"]
             + n_gold_e * 3
             + n_gold_a)
    detail["field_correct"] = correct
    detail["field_total"] = total
    detail["field_accuracy"] = round(correct / total, 4) if total else 0.0
    return detail


def main():
    ap = argparse.ArgumentParser(description="简历字段提取准确率评测（零 LLM）")
    ap.add_argument("--resumes", nargs="*", default=None, help="只评测指定简历 ID，如 B01 B02")
    ap.add_argument("--seed", default="data/eval/profile_seed.json")
    ap.add_argument("--resume-dir", default="data/eval/resumes")
    ap.add_argument("--json", default="data/eval/extraction_report.json")
    args = ap.parse_args()

    seed_path = ROOT / args.seed
    resume_dir = ROOT / args.resume_dir
    seeds = json.loads(seed_path.read_text(encoding="utf-8"))

    ids = args.resumes or sorted(seeds.keys())
    parser = ResumeParser()
    details = []
    for rid in ids:
        if rid not in seeds:
            print(f"[skip] 无真值: {rid}")
            continue
        fp = resume_dir / f"resume_{rid}.md"
        if not fp.exists():
            print(f"[skip] 无简历文件: {fp}")
            continue
        try:
            parsed = parser.parse(str(fp))
        except Exception as ex:
            print(f"[fail] {rid}: {ex}")
            continue
        d = eval_one(rid, seeds[rid], parsed)
        details.append(d)
        print(f"{rid}: 字段准确率={d['field_accuracy']:.3f}  "
              f"技能F1={d['skills']['f1']:.3f}  项目名={d['projects']['name_rate']:.2f}  "
              f"技术栈F1={d['projects']['tech_f1']:.3f}  教育={d['education']['school_rate']:.2f}  "
              f"成果={d['achievements']['rate']:.2f}")

    if not details:
        print("没有可评测的简历")
        return

    def agg(fn):
        return round(sum(fn(d) for d in details) / len(details), 4)

    summary = {
        "n_resumes": len(details),
        "field_accuracy": round(sum(d["field_correct"] for d in details)
                                / max(1, sum(d["field_total"] for d in details)), 4),
        "skills_f1": agg(lambda d: d["skills"]["f1"]),
        "skills_precision": agg(lambda d: d["skills"]["precision"]),
        "skills_recall": agg(lambda d: d["skills"]["recall"]),
        "project_name_rate": agg(lambda d: d["projects"]["name_rate"]),
        "project_count_exact_rate": agg(lambda d: d["projects"]["count_exact_match"]),
        "project_role_rate": agg(lambda d: d["projects"]["role_rate"]),
        "project_tech_f1": agg(lambda d: d["projects"]["tech_f1"]),
        "project_result_rate": agg(lambda d: d["projects"]["result_rate"]),
        "edu_school_rate": agg(lambda d: d["education"]["school_rate"]),
        "edu_degree_rate": agg(lambda d: d["education"]["degree_rate"]),
        "edu_major_rate": agg(lambda d: d["education"]["major_rate"]),
        "achievement_rate": agg(lambda d: d["achievements"]["rate"]),
    }

    report = {"generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "summary": summary, "detail": details}
    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n===== 汇总（%d 份简历）=====" % summary["n_resumes"])
    print(f"字段级总准确率      {summary['field_accuracy']:.4f}")
    print(f"技能 P/R/F1         {summary['skills_precision']:.3f} / "
          f"{summary['skills_recall']:.3f} / {summary['skills_f1']:.3f}")
    print(f"项目名命中率        {summary['project_name_rate']:.3f}")
    print(f"项目数一致率        {summary['project_count_exact_rate']:.3f}")
    print(f"项目角色命中率      {summary['project_role_rate']:.3f}")
    print(f"技术栈集合 F1       {summary['project_tech_f1']:.3f}")
    print(f"关键成果命中率      {summary['project_result_rate']:.3f}")
    print(f"教育 学校/学历/专业  {summary['edu_school_rate']:.3f} / "
          f"{summary['edu_degree_rate']:.3f} / {summary['edu_major_rate']:.3f}")
    print(f"成果命中率          {summary['achievement_rate']:.3f}")
    print(f"\n报告已写入 {out}")


if __name__ == "__main__":
    main()
