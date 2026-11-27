# -*- coding: utf-8 -*-
"""生成《毕业设计作品展示》文档 —— 按 11毕设作品展示文档模板（媒工）.docx 填表

模板结构（单页）：
    标题「媒体工程学院毕业设计作品展示」→ 中/英文论文题目 → 学生姓名/学号 →
    学院名称/专业 → 指导教师/职称 → 毕设作品简介（约 150 字）

用法：
    python scripts/make_showcase.py "输出路径.docx"
"""
import sys
from pathlib import Path

import docx
from docx.shared import Pt

TEMPLATE = Path(r"C:\Users\pd\Desktop\刘汪洋-毕设材料\04-学院规定与模板\11毕设作品展示文档模板（媒工）.docx")

TITLE_CN = "基于LangGraph的多Agent协作AI求职面试系统"
TITLE_EN = ("Design and Implementation of a LangGraph-based "
            "Multi-Agent AI Job-Seeking Interview System")

INTRO = (
    "本作品是基于 LangGraph 多 Agent 协作的 AI 求职面试系统，面向校园招聘场景，"
    "打通简历解析、网申填充、岗位匹配与面试问答全链路。系统以规则解析保证简历信息如实可溯源，"
    "以关键词、语义、知识图谱三路并行检索提升召回质量，"
    "以多 Agent 工作流约束大模型生成、避免编造，并以浏览器扩展实现表单一键填充。"
    "作品已完成可复现评测与端到端测试。"
)


def set_text(par, text):
    """替换段落文字，保留首个 run 的字体字号等格式"""
    if par.runs:
        par.runs[0].text = text
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.add_run(text)


def build(out_path: Path):
    d = docx.Document(str(TEMPLATE))
    ps = d.paragraphs

    # 论文题目（中文 / 英文）
    set_text(ps[2], "论文题目      " + TITLE_CN)
    set_text(ps[3], "              " + TITLE_EN)

    # 封面信息（保留模板的制表符排布）
    set_text(ps[5], "学生姓名：刘汪洋\t\t  学号：235703240\t")
    set_text(ps[6], "学院名称：媒体工程学院\t\t  专业：人工智能\t")
    set_text(ps[7], "指导教师：张丽\t     职称：副教授")

    # 作品简介
    set_text(ps[9], "毕设作品简介：" + INTRO)

    # 简介段落按正文习惯加首行缩进，读起来更整齐
    pf = ps[9].paragraph_format
    pf.first_line_indent = Pt(0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(out_path))
    print(f"已生成: {out_path}")
    print(f"简介字数: {len(INTRO)}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("作品展示文档.docx")
    build(target)
