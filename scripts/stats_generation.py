# -*- coding: utf-8 -*-
"""生成质量评测的统计汇总：中位数 + 四分位距，替代单看均值

用法：
    python scripts/stats_generation.py data/eval/generation_e2e_report_n15.json
"""
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def iqr(values):
    if len(values) < 4:
        return (min(values), max(values))
    q = st.quantiles(values, n=4)
    return (q[0], q[2])


def summarize_arm(rows):
    ok = [r for r in rows if r["answer_len"] >= 180]
    good = [r for r in ok if r.get("star", {}).get("complete")]
    grounded = [r for r in ok if (r.get("numbers") or {}).get("grounded_rate", 1) == 1]
    lat = [r["elapsed_ms"] / 1000 for r in rows]
    chars = [r["answer_len"] for r in rows]
    lat_lo, lat_hi = iqr(lat)
    ch_lo, ch_hi = iqr(chars)
    return {
        "n": len(rows),
        "valid": len(ok),
        "star_ok": len(good),
        "grounded_ok": len(grounded),
        "star_rate": round(len(good) / len(ok), 4) if ok else 0.0,
        "latency_median": round(st.median(lat), 1),
        "latency_iqr": (round(lat_lo, 1), round(lat_hi, 1)),
        "chars_median": round(st.median(chars)),
        "chars_iqr": (round(ch_lo), round(ch_hi)),
        "revisions": sum(int(r.get("revision_count") or 0) for r in rows),
        "errors": sum(1 for r in rows if r.get("error")),
    }


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/eval/generation_e2e_report.json"
    if not path.is_absolute():
        path = ROOT / path
    d = json.loads(path.read_text(encoding="utf-8"))

    print(f"文件: {path.name}   题数 n={d.get('n')}   模型 {d.get('model')}")
    print(f"生成时间: {d.get('generated_at')}\n")

    names = {"pipeline": "全量工作流", "pipeline_fast": "快速工作流", "single": "单次调用"}
    hdr = f"{'档位':<12}{'有效':>7}{'STAR':>9}{'可回溯':>8}{'字数中位(IQR)':>18}{'耗时中位(IQR)':>20}{'修订':>5}"
    print(hdr)
    print("-" * len(hdr))

    out = {}
    for key, cn in names.items():
        if key not in d:
            continue
        s = summarize_arm(d[key]["detail"])
        out[key] = s
        valid = f"{s['valid']}/{s['n']}"
        star = f"{s['star_ok']}/{s['valid']}"
        gnd = f"{s['grounded_ok']}/{s['valid']}"
        chars = f"{s['chars_median']} ({s['chars_iqr'][0]}-{s['chars_iqr'][1]})"
        lat = f"{s['latency_median']:.1f}s ({s['latency_iqr'][0]}-{s['latency_iqr'][1]})"
        print(f"{cn:<12}{valid:>7}{star:>9}{gnd:>8}{chars:>18}{lat:>20}{s['revisions']:>5}")

    # 相对差异
    if "pipeline" in out and "single" in out:
        p, s1 = out["pipeline"], out["single"]
        print(f"\n全量 vs 单次：字数 {p['chars_median']} / {s1['chars_median']} = "
              f"{p['chars_median'] / max(1, s1['chars_median']):.2f} 倍；"
              f"延迟 {p['latency_median'] / max(0.1, s1['latency_median']):.1f} 倍")
    if "pipeline" in out and "pipeline_fast" in out:
        p, f = out["pipeline"], out["pipeline_fast"]
        print(f"全量 vs 快速：字数 {p['chars_median']} / {f['chars_median']} = "
              f"{p['chars_median'] / max(1, f['chars_median']):.2f} 倍；"
              f"延迟 {p['latency_median'] / max(0.1, f['latency_median']):.1f} 倍")

    # 写回 JSON 便于论文引用
    d["stats_median_iqr"] = out
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n统计结果已写入 {path.name} 的 stats_median_iqr 字段")


if __name__ == "__main__":
    main()
