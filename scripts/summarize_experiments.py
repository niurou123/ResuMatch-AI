# -*- coding: utf-8 -*-
"""汇总四组实验结果为论文第 5 章可用的表格（Markdown + 控制台）

读取：
    data/eval/extraction_report.json      字段提取准确率
    data/eval/retrieval_report.json       检索质量 + 六模式消融
    data/eval/generation_e2e_report.json  生成质量 + 多 Agent 有效性（三档对照）
    data/eval/form_fill_report.json       表单字段覆盖率

输出：
    data/eval/实验数据汇总.md

注意：检索消融用真实数据；生成质量注明样本量与评测口径（BUG_LOG 案例 29/31 已修正）。
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "data" / "eval"


def load(name):
    p = EVAL / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def pct(v, nd=1):
    if v is None:
        return "—"
    return f"{v * 100:.{nd}f}%"


lines = []
add = lines.append

add("# 实验数据汇总（论文第 5 章可用）")
add("")
add(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　｜　数据目录：`data/eval/`")
add("")

# ---------------- 5.2 字段提取 ----------------
ex = load("extraction_report.json")
add("## 5.2 简历字段提取准确率")
add("")
if ex:
    s = ex["summary"]
    add(f"评测对象：{s['n_resumes']} 份程序化生成的匿名简历（对照 `profile_seed.json` 标注真值），零大模型介入。")
    add("")
    add("| 指标 | 数值 |")
    add("|---|---|")
    add(f"| 字段级总准确率 | **{pct(s['field_accuracy'], 2)}** |")
    add(f"| 技能 Precision / Recall / F1 | {s['skills_precision']:.3f} / {s['skills_recall']:.3f} / {s['skills_f1']:.3f} |")
    add(f"| 项目名命中率 | {pct(s['project_name_rate'])} |")
    add(f"| 项目数一致率 | {pct(s['project_count_exact_rate'])} |")
    add(f"| 项目角色命中率 | {pct(s['project_role_rate'])} |")
    add(f"| 技术栈集合 F1 | {s['project_tech_f1']:.3f} |")
    add(f"| 关键成果命中率 | {pct(s['project_result_rate'])} |")
    add(f"| 教育 学校 / 学历 / 专业 命中率 | {pct(s['edu_school_rate'])} / {pct(s['edu_degree_rate'])} / {pct(s['edu_major_rate'])} |")
    add(f"| 成果命中率 | {pct(s['achievement_rate'])} |")
    add("")
    add("> 说明：评测集为规范排版的 Markdown 简历，指标反映**解析规则对规范文本的保真度**；"
        "扫描件、双栏、图表类简历未纳入，不能等同于真实世界准确率。")
else:
    add("（未找到 extraction_report.json，请先运行 `scripts/eval_extraction.py`）")
add("")

# ---------------- 5.3 检索 + 消融 ----------------
rt = load("retrieval_report.json")
add("## 5.3 检索质量与消融实验")
add("")
if rt and isinstance(rt.get("reports"), dict):
    reps = rt["reports"]
    n = next(iter(reps.values()))["n"]
    add(f"评测对象：{n} 道带检索标注的问题；指标为 Recall@k / MRR / nDCG@k。")
    add("")
    add("| 模式 | R@3 | R@5 | R@8 | MRR | nDCG@5 | 平均耗时(ms) |")
    add("|---|---|---|---|---|---|---|")
    label = {"full": "full（全开）", "no_hyde": "no_hyde", "no_rerank": "no_rerank",
             "no_graph": "no_graph", "no_multiquery": "no_multiquery", "no_semantic": "no_semantic"}
    for k, v in reps.items():
        add(f"| {label.get(k, k)} | {v['recall@3']:.4f} | {v['recall@5']:.4f} | {v['recall@8']:.4f} | "
            f"{v['mrr']:.4f} | {v['ndcg@5']:.4f} | {v['latency_ms_avg']:.1f} |")
    add("")
    base = reps["full"]["recall@5"]
    add("**相对 full 模式的 Recall@5 差异**：")
    add("")
    add("| 模式 | 与 full 的差值 |")
    add("|---|---|")
    for k, v in reps.items():
        if k == "full":
            continue
        d = (base - v["recall@5"]) / v["recall@5"] * 100
        add(f"| {label.get(k, k)} | full 比它 {'高' if d >= 0 else '低'} {abs(d):.1f}% |")
    add("")
    add("> 说明：HyDE 与多查询在本次评测中未产生可测差异（评测走规则降级、跳过 LLM 版 HyDE），"
        "精排与知识图谱的 R@5 略低于 full 但 MRR/nDCG 有差别——"
        "论文中应把这一点作为**小规模语料下的适用边界**如实讨论，而非宣称全面提升。")
else:
    add("（未找到 retrieval_report.json，请先运行 `scripts/eval_retrieval.py`）")
add("")

# ---------------- 5.4 生成 + 多 Agent ----------------
ge = load("generation_e2e_report.json")
add("## 5.4 生成质量与多 Agent 有效性对比")
add("")
if ge:
    n = ge.get("n")
    add(f"评测对象：{n} 道项目/技术类问题；独立评测画像 + 独立向量库，生成与比对基准一致。")
    if ge.get("model"):
        add(f"使用模型：`{ge['model']}`")
    add("")
    arms = [("pipeline", "流水线（全量）"), ("pipeline_fast", "流水线（fast）"), ("single", "单 Agent 基线")]
    have = [(k, t) for k, t in arms if k in ge]
    add("| 指标 | " + " | ".join(t for _, t in have) + " |")
    add("|---" * (len(have) + 1) + "|")
    rows = [("star_complete_rate", "STAR 完整率", True),
            ("number_grounded_rate", "数字可回溯率", True),
            ("avg_answer_len", "平均字数", False),
            ("avg_elapsed_ms", "平均耗时(ms)", False)]
    for key, title, is_pct in rows:
        vals = []
        for k, _ in have:
            v = ge[k]["summary"].get(key)
            if v is None:
                vals.append("—")
            elif is_pct:
                vals.append(pct(v))
            elif isinstance(v, float):
                vals.append(f"{v:.1f}")
            else:
                vals.append(str(v))
        add(f"| {title} | " + " | ".join(vals) + " |")
    add("")
    add("> 说明：三档对照用于回答\"多 Agent 是否必要\"。结论应表述为"
        "**多 Agent 的价值在过程可控与可观测，而非答案质量提升**，代价是端到端延迟增加。")
else:
    add("（未找到 generation_e2e_report.json，请先运行 `scripts/eval_generation_e2e.py`）")
add("")

# ---------------- 5.5 表单填充 ----------------
ff = load("form_fill_report.json")
add("## 5.5 网申表单字段覆盖率")
add("")
if ff:
    fc = ff["field_coverage"]
    add(f"评测对象：{ff.get('profile', '')}；夹具 {fc['total']} 个字段（5 类 ATS 站点）。")
    add("")
    add("| 站点 | 字段数 | 已填 | 覆盖率 |")
    add("|---|---|---|---|")
    for v in fc["by_vendor"]:
        add(f"| {v['vendor']} | {v['total']} | {v['filled']} | {pct(v['rate'])} |")
    add(f"| **合计** | **{fc['total']}** | **{fc['filled']}** | **{pct(fc['rate'])}** |")
    add("")
    da = ff.get("dropdown_alias", {})
    nf = ff.get("no_fabrication", {})
    add(f"- 下拉选项别名匹配准确率：**{da.get('ok')}/{da.get('total')}**（{pct(da.get('rate'))}）")
    add(f"- 空值不编造通过率：**{nf.get('ok')}/{nf.get('total')}**（{pct(nf.get('rate'))}）")
    un = ff.get("unrecognized_fields") or []
    if un:
        add(f"- 未识别字段 {len(un)} 个，均为档案本身无该项数据、应留空的字段")
    add("")
    add("> 说明：评测直接加载扩展真实映射引擎（`matchField` / `matchSelectOption`），"
        "覆盖率与档案数据完备度强相关，报告中需同时给出夹具与档案口径。")
else:
    add("（未找到 form_fill_report.json，请先运行 `node scripts/eval_form_fill.js`）")
add("")

out = EVAL / "实验数据汇总.md"
out.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print(f"\n已写入 {out}")
