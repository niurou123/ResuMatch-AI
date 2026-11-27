# -*- coding: utf-8 -*-
"""参考文献批量核验 — 从 .docx / .txt 读取文献表，逐条对 Crossref / arXiv 核对

为什么需要它：
    GB/T 7714 的文献条目是人工敲进去的，卷期页、DOI、会议名极易出错，而这类错误在
    评阅/抽检时是硬伤（浙江省抽检评议要素 5.2「参考文献是否规范准确」）。
    本脚本把「文献表」当作待测数据，逐条回源核对，输出可复核的报告。

核验策略（按优先级，全部走公开 API，无需 key）：
    1. 条目里有 DOI            → Crossref /works/{doi}，逐字段比对年份与页码
    2. 条目里有 arXiv 编号     → arXiv Atom API，比对题名
    3. 其余（会议/期刊/标准）  → Crossref 书目检索，取最高相关结果，
                                再用题名归一化匹配判断是否命中
同源工具参考（GitHub）：sckott/habanero（Crossref 客户端）、lukasswab/arxiv.py、
danielnsilva/semanticscholar；本项目直接走 REST，零依赖、可离线改造成缓存版。

用法：
    python scripts/verify_refs.py 文档.docx
    python scripts/verify_refs.py 文档.docx --json data/eval/ref_verify.json
    python scripts/verify_refs.py refs.txt --limit 5
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "ResuMatchRefVerify/1.0 (mailto:student@example.com)"}
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s,;，；]+)")
ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})", re.IGNORECASE)
REF_PREFIX = re.compile(r"^\s*\[(\d+)\]\s*")
YEAR_RE = re.compile(r"(19|20)\d{2}")
PAGES_RE = re.compile(r"(\d{1,4})\s*[-–—]\s*(\d{1,4})")


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fa5]", "", (s or "").lower())


def get(url, timeout=35, tries=4):
    """带退避的 GET：Crossref 对连续请求会 429，重试可避免把限流误判成无记录。"""
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as ex:
            last = ex
            time.sleep(2 + 2 * k)
    raise last


def crossref_doi(doi: str):
    try:
        d = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))
        m = d["message"]
        return {
            "title": (m.get("title") or [""])[0],
            "container": (m.get("container-title") or [""])[0],
            "year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
            "volume": m.get("volume"), "issue": m.get("issue"), "page": m.get("page"),
            "doi": m.get("DOI"),
        }
    except Exception:
        return None


def crossref_search(text: str):
    p = {"query.bibliographic": text, "rows": 3,
         "select": "DOI,title,container-title,issued,volume,issue,page"}
    try:
        d = json.loads(get("https://api.crossref.org/works?" + urllib.parse.urlencode(p)))
    except Exception as ex:
        print(f"      [Crossref 查询失败] {str(ex)[:60]}")
        return None          # None = 接口异常；[] = 真的没有结果
    out = []
    for it in d["message"]["items"]:
        out.append({
            "title": (it.get("title") or [""])[0],
            "container": (it.get("container-title") or [""])[0],
            "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
            "volume": it.get("volume"), "issue": it.get("issue"), "page": it.get("page"),
            "doi": it.get("DOI"),
        })
    return out


def arxiv_lookup(aid: str):
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(get(
            "https://export.arxiv.org/api/query?id_list=" + aid))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        e = root.find("a:entry", ns)
        if e is None:
            return None
        return {"title": " ".join(e.find("a:title", ns).text.split()),
                "year": e.find("a:published", ns).text[:4]}
    except Exception:
        return None


def verify_one(ref: str, idx: int):
    """返回 (status, note, matched)"""
    doi_m = DOI_RE.search(ref)
    ax_m = ARXIV_RE.search(ref)

    if doi_m:
        doi = doi_m.group(1).rstrip(".")
        m = crossref_doi(doi)
        if not m:
            return "❌", f"DOI 无法解析: {doi}", None
        notes = []
        years = YEAR_RE.findall(ref)
        if m["year"] and str(m["year"]) not in ref:
            notes.append(f"年份不一致（Crossref={m['year']}）")
        if m.get("page"):
            pg = re.sub(r"\s", "", m["page"])
            if pg and pg not in re.sub(r"\s", "", ref):
                notes.append(f"页码不一致（Crossref={m['page']}）")
        if m.get("volume") and str(m["volume"]) not in ref:
            notes.append(f"卷号不一致（Crossref={m['volume']}）")
        return ("✅" if not notes else "⚠️"), ("; ".join(notes) or "DOI 与出版信息一致"), m

    if ax_m:
        aid = ax_m.group(1)
        m = arxiv_lookup(aid)
        if not m:
            return "❌", f"arXiv 未找到: {aid}", None
        ok = norm(m["title"])[:40] in norm(ref) or norm(ref).find(norm(m["title"])[:30]) >= 0
        return ("✅" if ok else "⚠️"), ("arXiv 题名匹配" if ok else f"题名可能不符：{m['title'][:50]}"), m

    # 无 DOI / arXiv：Crossref 书目检索
    found = crossref_search(ref)
    if found is None:
        return "⚠️", "Crossref 接口异常（限流），本条未完成核验，建议稍后重跑", None
    for cand in found[:3]:
        t = norm(cand["title"])
        if t and (t in norm(ref) or norm(ref)[:60] in t or t[:30] in norm(ref)):
            notes = []
            if cand["year"] and str(cand["year"]) not in ref:
                notes.append(f"年份不一致（Crossref={cand['year']}）")
            return ("✅" if not notes else "⚠️"), "; ".join(notes) or "题名匹配", cand
    return "⚠️", "Crossref 未匹配到可靠记录（需人工确认）", None


def _iter_all_paragraphs(doc):
    """遍历正文 + 表格（含嵌套表格）里的全部段落

    文献综述/开题报告的文献表在 1×1 表格单元格里，doc.paragraphs 读不到，
    必须递归表格，否则会得到 0 条文献。
    """
    for p in doc.paragraphs:
        yield p

    def walk_table(tb, depth=0):
        if depth > 3:
            return
        for row in tb.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p
                for inner in cell.tables:
                    yield from walk_table(inner, depth + 1)

    for tb in doc.tables:
        yield from walk_table(tb)


def read_refs(path: Path):
    if path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(path))
        lines = [(p.text or "").strip() for p in _iter_all_paragraphs(doc)]
    else:
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
    refs = []
    for l in lines:
        if REF_PREFIX.match(l) and len(l) > 20:
            refs.append(l)
    return refs


def main():
    ap = argparse.ArgumentParser(description="参考文献批量核验（Crossref / arXiv）")
    ap.add_argument("file", help=".docx 或 .txt（含 [1] [2] … 文献表）")
    ap.add_argument("--limit", type=int, default=0, help="只核验前 N 条")
    ap.add_argument("--json", default="", help="结果写入 JSON")
    ap.add_argument("--sleep", type=float, default=0.35, help="每条之间的间隔秒数（避免限流）")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {path}")
        sys.exit(1)

    refs = read_refs(path)
    if args.limit:
        refs = refs[:args.limit]
    print(f"共 {len(refs)} 条文献，开始逐条回源核验（Crossref / arXiv）\n")

    ok = warn = bad = 0
    rows = []
    for ref in refs:
        m0 = REF_PREFIX.match(ref)
        idx = int(m0.group(1)) if m0 else 0
        status, note, matched = verify_one(ref, idx)
        if status == "✅":
            ok += 1
        elif status == "⚠️":
            warn += 1
        else:
            bad += 1
        rows.append({"no": idx, "status": status, "note": note,
                     "ref": ref[:120], "matched": matched})
        title = (matched or {}).get("title", "")[:52]
        print(f"[{idx:>2}] {status} {note}")
        if title:
            print(f"      命中: {title}")
        time.sleep(max(0.0, args.sleep))

    print(f"\n===== 汇总：✅ {ok}   ⚠️ {warn}   ❌ {bad}   合计 {len(refs)} =====")
    print("说明：⚠️ 表示 API 未给出可靠匹配或字段略有差异，需人工复核；❌ 表示可定位到明确错误。")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"file": str(path), "total": len(refs),
                        "ok": ok, "warn": warn, "bad": bad, "rows": rows},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"报告已写入 {args.json}")


if __name__ == "__main__":
    main()
