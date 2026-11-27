# -*- coding: utf-8 -*-
"""抓取公开简历语料到 data/eval/resumes_ext/（用于解析鲁棒性评测）

数据来源（均为公开数据集，非个人隐私爬取）
----------------------------------------
1. opensporks/resumes       许可 CC0-1.0（公有领域），字段 Resume_str / Category
2. d4rk3r/resumes-raw-pdf   许可 MIT，字段 pdf / label（PDF 二进制，用于测 PDF 解析路径）

输出
----
data/eval/resumes_ext/resume_E###.txt   —— 纯文本真实简历
data/eval/resumes_ext/resume_P###.pdf   —— PDF 真实简历
data/eval/resumes_ext/manifest.json     —— 来源、许可、行号、SHA256（可复核）

用法
----
    python scripts/fetch_external_resumes.py --text 40 --pdf 10
    python scripts/fetch_external_resumes.py --text 20 --pdf 0 --fresh
"""
import argparse
import hashlib
import json
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "eval" / "resumes_ext"
UA = {"User-Agent": "ResuMatch-EvalBot/1.0"}
SERVER = "https://datasets-server.huggingface.co"

TEXT_DS = {"id": "opensporks/resumes", "license": "CC0-1.0", "field": "Resume_str",
           "label": "Category"}
PDF_DS = {"id": "d4rk3r/resumes-raw-pdf", "license": "MIT", "field": "pdf", "label": "label"}


def get_json(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as ex:
            print(f"    retry {k+1}/{tries}: {str(ex)[:70]}")
            time.sleep(3 + 3 * k)
    return None


def get_bytes(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read()
        except Exception as ex:
            print(f"    retry {k+1}/{tries}: {str(ex)[:70]}")
            time.sleep(3 + 3 * k)
    return None


def fetch_rows(ds_id, n, offset=0):
    """按 100 行一页取数据（datasets-server 单次上限 100）"""
    rows, got = [], 0
    while got < n:
        want = min(100, n - got)
        url = (f"{SERVER}/rows?dataset={urllib.parse.quote(ds_id)}"
               f"&config=default&split=train&offset={offset + got}&length={want}")
        d = get_json(url)
        if not d:
            break
        batch = d.get("rows") or []
        if not batch:
            break
        rows.extend(batch)
        got += len(batch)
        time.sleep(0.8)
    return rows[:n]


def main():
    ap = argparse.ArgumentParser(description="抓取公开简历语料（CC0 / MIT）")
    ap.add_argument("--text", type=int, default=40, help="文本简历数量")
    ap.add_argument("--pdf", type=int, default=10, help="PDF 简历数量")
    ap.add_argument("--fresh", action="store_true", help="清空目录后重建")
    args = ap.parse_args()

    if args.fresh and OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []

    # ---------- 文本简历 ----------
    if args.text > 0:
        print(f"抓取文本简历 {args.text} 份（{TEXT_DS['id']}，许可 {TEXT_DS['license']}）")
        rows = fetch_rows(TEXT_DS["id"], args.text)
        for i, item in enumerate(rows):
            row = item.get("row", {})
            text = row.get(TEXT_DS["field"]) or ""
            if not text.strip():
                continue
            name = f"resume_E{i + 1:03d}.txt"
            fp = OUT / name
            fp.write_text(text, encoding="utf-8")
            manifest.append({
                "file": name, "kind": "text", "dataset": TEXT_DS["id"],
                "license": TEXT_DS["license"], "row_index": item.get("row_idx"),
                "label": row.get(TEXT_DS["label"], ""), "chars": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            })
            print(f"  {name}  {len(text)} 字符  [{row.get(TEXT_DS['label'], '')}]")

    # ---------- PDF 简历 ----------
    if args.pdf > 0:
        print(f"\n抓取 PDF 简历 {args.pdf} 份（{PDF_DS['id']}，许可 {PDF_DS['license']}）")
        rows = fetch_rows(PDF_DS["id"], args.pdf)
        ok = 0
        for i, item in enumerate(rows):
            row = item.get("row", {})
            pdf = row.get(PDF_DS["field"])
            if not isinstance(pdf, dict):
                continue
            src = pdf.get("src")
            if not src:
                continue
            data = get_bytes(src)
            if not data or not data[:4] == b"%PDF":
                continue
            name = f"resume_P{i + 1:03d}.pdf"
            (OUT / name).write_bytes(data)
            manifest.append({
                "file": name, "kind": "pdf", "dataset": PDF_DS["id"],
                "license": PDF_DS["license"], "row_index": item.get("row_idx"),
                "label": row.get(PDF_DS["label"], ""), "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()[:16], "source_url": src,
            })
            ok += 1
            print(f"  {name}  {len(data) // 1024} KB  [{row.get(PDF_DS['label'], '')}]")
            time.sleep(0.4)
        print(f"  PDF 成功 {ok}/{len(rows)}")

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    n_text = sum(1 for m in manifest if m["kind"] == "text")
    n_pdf = sum(1 for m in manifest if m["kind"] == "pdf")
    print(f"\n共 {len(manifest)} 份（文本 {n_text} / PDF {n_pdf}）-> {OUT}")
    print(f"清单: {manifest_path}")


if __name__ == "__main__":
    main()
