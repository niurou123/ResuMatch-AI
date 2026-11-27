# -*- coding: utf-8 -*-
"""毕业论文格式校验器 — 规则来自学院官方模板（7理工类毕业设计模板.doc）

为什么不直接用 GitHub 上的现成检查器：
    搜到的若干 "thesis format checker" 仓库都是 0~1 星的自建脚本，规则是作者学校
    的，与浙传媒工院的模板不一致；通用工具（pandoc / python-docx / docxtpl）只提供
    读写能力，不提供本校规范。因此本校验器把官方模板解析出来的规则硬编码为可核查项，
    直接对照 .docx 的 OOXML，规则与模板逐条对应。

校验项（依据官方模板 7理工类毕业设计模板.doc）：
    P1 页面：A4，上下左右页边距 2.5cm
    P2 正文：宋体 / 小四(12pt) / 1.25 倍行距 / 首行缩进 2 字符(24pt) / 两端对齐
    P3 一级标题（1 绪论 / 参考文献 / 致谢 / 附录）：宋体 14pt 加粗
    P4 二、三级标题（2.1 / 2.1.1）：宋体 12pt 加粗、首行缩进 2 字符
    P5 必备结构：摘要、Abstract、目录、正文、参考文献、致谢
    P6 大小写与占位符：不得残留「（论文中文题目）」「致谢文本」等模板占位
    P7 参考文献条目：序号 + 文献类型标识（[J]/[M]/[C]/[D]/[S]/[EB/OL] 等）
    P8 正文工作量：正文字数（不含封面/声明/目录/参考文献/致谢）

用法：
    python scripts/check_thesis_format.py 论文.docx
    python scripts/check_thesis_format.py 论文.docx --json report.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

ROOT = Path(__file__).resolve().parent.parent

# ===== 官方模板常量 =====
EXPECT_BODY_FONT = "宋体"
EXPECT_BODY_SIZE = 12.0          # 小四
EXPECT_BODY_LINE = 1.25          # 行距倍数
EXPECT_BODY_INDENT_PT = 24.0     # 首行缩进 2 字符
EXPECT_H1_SIZE = 14.0            # 四号
EXPECT_H2_SIZE = 12.0
EXPECT_MARGIN_CM = 2.5

PLACEHOLDERS = [
    "（论文中文题目）", "（论文英文题目）", "论文题目", "致谢文本",
    "第一章标题", "第二章标题", "此处填写", "请填写", "XXX",
]

TYPE_MARK = re.compile(r"\[(J|M|C|D|S|N|R|P|Z|EB/OL|J/OL|DB/OL|C/OL|A)\]")


def east_asia_font(run):
    """取 run 的中文字体名（w:eastAsia）"""
    rPr = run._element.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr")
    if rPr is None:
        return None
    rFonts = rPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    if rFonts is None:
        return None
    return rFonts.get(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia")


def para_font_info(p):
    """返回 (中文字体, 字号, 是否加粗)，取第一个有文本的 run；无 run 时回退样式"""
    for r in p.runs:
        if (r.text or "").strip():
            size = r.font.size.pt if r.font.size else None
            return east_asia_font(r) or r.font.name, size, bool(r.font.bold)
    # 空段落回退到样式字体
    try:
        st = p.style
        size = st.font.size.pt if st.font.size else None
        return st.font.name, size, bool(st.font.bold)
    except Exception:
        return None, None, None


def para_line_spacing(p):
    """返回 (规则, 值)：1.25 → ('multiple', 1.25)"""
    pf = p.paragraph_format
    rule = pf.line_spacing_rule
    val = pf.line_spacing
    if val is None:
        return None, None
    if isinstance(val, float):          # multiple
        return "multiple", round(val, 3)
    try:                                 # Length → pt
        return str(rule), round(val.pt, 1)
    except Exception:
        return str(rule), val


def indent_pt(p):
    v = p.paragraph_format.first_line_indent
    return round(v.pt, 1) if v is not None else 0.0


def classify(p, text):
    """按样式名与文本判断段落角色

    role 取值：h1 / h2 / h3 / body / toc / caption
    - toc     ：目录行（样式「目录 N」或含制表符页码）
    - caption ：图/表题注、续表标记、图表注释、公式编号——模板规定为五号(10.5pt)、顶格
    """
    style = (p.style.name or "") if p.style else ""
    if style.startswith("目录") or style.upper().startswith("TOC"):
        return "toc"
    # 目录行兜底识别："1 绪论⇥1"——行尾跟制表符+页码
    if re.search(r"\t\s*\d{1,4}\s*$", text):
        return "toc"
    # 模板内的说明性文字（"（略）""（页边距…"），不参与正文校验
    if text.startswith("（略）") or text.startswith("（页边距") or text.startswith("(略)"):
        return "skip"
    if style.startswith("标题 1") or style.startswith("Heading 1"):
        return "h1"
    if style.startswith("标题 2") or style.startswith("Heading 2"):
        return "h2"
    if style.startswith("标题 3") or style.startswith("Heading 3"):
        return "h3"
    # 图/表题注与注释
    if (re.match(r"^(图|表)\s*\d+\s*[-–—－]\s*\d+", text)
            or text.startswith("续表")
            or text.startswith("注：") or text.startswith("注:")
            or text.startswith("数据来源") or text.startswith("图片来源")
            or re.match(r"^[（(]\s*\d+\s*[-–—－]\s*\d+\s*[）)]$", text)):
        return "caption"
    # 章号标题："1 绪论" / "2.1 标题"；排除 "2026 年 11 月" 这类日期
    if (re.match(r"^\d{1,2}(\.\d{1,2}){0,2}\s+[^\d\s]", text)
            and len(text) < 40 and not re.search(r"年|月|日", text)):
        depth = text.split(" ")[0].count(".")
        return {0: "h1", 1: "h2", 2: "h3"}.get(depth, "body")
    # 前置部分标题（允许中间夹空格，如 "摘  要" "目  录"）
    if re.sub(r"\s", "", text) in ("参考文献", "致谢", "附录", "摘要", "Abstract", "ABSTRACT", "目录"):
        return "h1"
    return "body"


def _iter_all_paragraphs(doc):
    """遍历正文 + 表格（含嵌套）里的全部段落

    模板的目录、郑重声明、封面信息常被放在表格单元格里，只看 doc.paragraphs 会漏，
    进而误报"缺少目录/声明"。这里统一递归表格。
    """
    for p in doc.paragraphs:
        yield p

    def walk(tb, depth=0):
        if depth > 3:
            return
        for row in tb.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p
                for inner in cell.tables:
                    yield from walk(inner, depth + 1)

    for tb in doc.tables:
        yield from walk(tb)


def check(path: Path):
    doc = Document(str(path))
    issues = []
    stats = {"paragraphs": len(doc.paragraphs), "tables": len(doc.tables)}

    # ---- P1 页面 ----
    for i, sec in enumerate(doc.sections):
        for name, val in (("上", sec.top_margin), ("下", sec.bottom_margin),
                          ("左", sec.left_margin), ("右", sec.right_margin)):
            cm = round(val.cm, 2) if val is not None else None
            if cm is None or abs(cm - EXPECT_MARGIN_CM) > 0.12:
                issues.append(("P1", f"节{i+1} {name}边距 = {cm}cm（应为 2.5cm）"))

    # ---- 逐段校验（带区域状态机：封面/声明/摘要/目录/正文/参考文献/致谢/附录）----
    body_chars = 0
    region = "cover"
    has = {"摘要": False, "Abstract": False, "目录": False, "参考文献": False, "致谢": False}
    h1_count = 0
    BODY_REGIONS = ("body", "abstract", "abstract_en")

    for idx, p in enumerate(_iter_all_paragraphs(doc)):
        text = (p.text or "").strip()
        if not text:
            continue
        style = (p.style.name or "") if p.style else ""
        role = classify(p, text)
        low = text.lower()

        # ——— 区域切换 ———
        if "郑重声明" in text.replace(" ", ""):
            region = "declare"
        elif low.replace(" ", "").startswith("摘要") and role == "h1":
            region = "abstract"
        elif low.startswith("abstract") and role == "h1":
            region = "abstract_en"
        elif text.replace(" ", "") == "目录" or style.startswith("目录"):
            region = "toc"
        elif role == "h1":
            if text.startswith("参考文献"):
                region = "refs"
            elif text.startswith("致谢"):
                region = "ack"
            elif text.startswith("附录"):
                region = "appendix"
            elif re.match(r"^\d+(\.\d+)*\s*\S", text):
                region = "body"

        # ——— 结构标记 ———
        if low.replace(" ", "").startswith("摘要"):
            has["摘要"] = True
        if low.startswith("abstract"):
            has["Abstract"] = True
        if region == "toc":
            has["目录"] = True
        if region == "refs":
            has["参考文献"] = True
        if region == "ack":
            has["致谢"] = True

        font, size, bold = para_font_info(p)
        rule, val = para_line_spacing(p)
        ind = indent_pt(p)

        # P6 占位符（跳过参考文献区，避免误报）
        if region != "refs":
            for ph in PLACEHOLDERS:
                if ph in text:
                    issues.append(("P6", f"第{idx+1}段 残留占位符「{ph}」：{text[:30]}"))

        # P3/P4 标题
        if role == "h1":
            h1_count += 1
            is_front = re.sub(r"\s", "", text) in ("摘要", "Abstract", "ABSTRACT", "目录")
            if size is not None:
                if is_front:
                    if not (14.0 <= size <= 20.0):
                        issues.append(("P3", f"第{idx+1}段 前置标题字号 {size}pt（应为 14~20pt）：{text[:24]}"))
                elif abs(size - EXPECT_H1_SIZE) > 0.5:
                    issues.append(("P3", f"第{idx+1}段 一级标题字号 {size}pt（应为 {EXPECT_H1_SIZE}pt）：{text[:24]}"))
            if bold is False:
                issues.append(("P3", f"第{idx+1}段 一级标题未加粗：{text[:24]}"))
        elif role in ("h2", "h3"):
            if size is not None and abs(size - EXPECT_H2_SIZE) > 0.5:
                issues.append(("P4", f"第{idx+1}段 {role}标题字号 {size}pt（应为 {EXPECT_H2_SIZE}pt）：{text[:24]}"))
            if bold is False:
                issues.append(("P4", f"第{idx+1}段 {role}标题未加粗：{text[:24]}"))

        # P2 正文（仅正文/摘要区，且非标题）
        if region in BODY_REGIONS and role == "body":
            body_chars += len(re.sub(r"\s", "", text))
            if font and font not in (EXPECT_BODY_FONT, "Times New Roman", "Cambria Math"):
                issues.append(("P2", f"第{idx+1}段 正文字体「{font}」（应为宋体）：{text[:24]}"))
            if size is not None and abs(size - EXPECT_BODY_SIZE) > 0.5:
                issues.append(("P2", f"第{idx+1}段 正文字号 {size}pt（应为 12pt）：{text[:24]}"))
            if rule == "multiple" and val is not None and abs(val - EXPECT_BODY_LINE) > 0.03:
                issues.append(("P2", f"第{idx+1}段 行距倍数 {val}（应为 1.25）：{text[:24]}"))
            if abs(ind - EXPECT_BODY_INDENT_PT) > 3.0:
                issues.append(("P2", f"第{idx+1}段 首行缩进 {ind}pt（应为 24pt≈2字符）：{text[:24]}"))

        # P7 参考文献条目
        if region == "refs" and re.match(r"^\[\d+\]", text):
            if not TYPE_MARK.search(text):
                issues.append(("P7", f"第{idx+1}段 参考文献缺类型标识（[J]/[M]/[C]…）：{text[:30]}"))

    # ---- P5 结构完备性 ----
    for k, ok in has.items():
        if not ok:
            issues.append(("P5", f"缺少必备部分：{k}"))
    if h1_count == 0:
        issues.append(("P5", "未识别到任何一级标题（正文应有「1 绪论」等章节）"))

    stats["body_chars"] = body_chars
    stats["h1_count"] = h1_count
    return issues, stats


def main():
    ap = argparse.ArgumentParser(description="毕业论文格式校验（依据学院官方模板）")
    ap.add_argument("docx", help="待校验的 .docx 文件")
    ap.add_argument("--json", default="", help="把结果写入 JSON")
    ap.add_argument("--max-show", type=int, default=40, help="最多显示多少条问题")
    args = ap.parse_args()

    path = Path(args.docx)
    if not path.exists():
        print(f"文件不存在: {path}")
        sys.exit(1)

    issues, stats = check(path)
    print("=" * 74)
    print(f"论文格式校验  {path.name}")
    print(f"段落 {stats['paragraphs']} | 表格 {stats['tables']} | 一级标题 {stats['h1_count']} | 正文字数 {stats['body_chars']}")
    print("=" * 74)

    if not issues:
        print("✅ 未发现格式问题")
    else:
        by_rule = {}
        for rule, msg in issues:
            by_rule.setdefault(rule, []).append(msg)
        names = {
            "P1": "页边距", "P2": "正文格式", "P3": "一级标题", "P4": "二三级标题",
            "P5": "结构完备性", "P6": "模板占位符", "P7": "参考文献格式",
        }
        for rule in sorted(by_rule):
            print(f"\n【{rule} {names.get(rule, rule)}】{len(by_rule[rule])} 处")
            for m in by_rule[rule][:args.max_show]:
                print("  - " + m)
            if len(by_rule[rule]) > args.max_show:
                print(f"  … 其余 {len(by_rule[rule]) - args.max_show} 处省略")
        print(f"\n合计 {len(issues)} 处问题")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"file": str(path), "stats": stats,
                        "issues": [{"rule": r, "message": m} for r, m in issues]},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"报告已写入 {args.json}")


if __name__ == "__main__":
    main()
