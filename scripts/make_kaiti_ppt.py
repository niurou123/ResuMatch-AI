# -*- coding: utf-8 -*-
"""生成开题答辩 PPT（16:9，白底黑字 + 单点蓝，与系统界面同一套视觉）

用法：
    python scripts/make_kaiti_ppt.py "输出路径.pptx"
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------- 视觉令牌 ----------
INK = RGBColor(0x1F, 0x23, 0x29)
INK_2 = RGBColor(0x4E, 0x59, 0x69)
INK_3 = RGBColor(0x86, 0x90, 0x9C)
BLUE = RGBColor(0x0B, 0x6B, 0xCB)
BLUE_LIGHT = RGBColor(0xE8, 0xF1, 0xFB)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xE5, 0xE6, 0xEB)
FONT = "微软雅黑"

TITLE = "基于LangGraph的多Agent协作AI求职面试系统"
TITLE_EN = "Design and Implementation of a LangGraph-based Multi-Agent AI Job-Seeking Interview System"
STUDENT = "刘汪洋"
STUDENT_ID = "235703240"
MAJOR = "人工智能"
COLLEGE = "媒体工程学院"
ADVISOR = "张丽  副教授"
DATE = "2026 年 11 月"

W, H = Inches(13.333), Inches(7.5)


def txbox(slide, left, top, width, height, text, size=18, bold=False,
          color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.25):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    r.font.name = FONT
    return box


def rect(slide, left, top, width, height, fill, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    shp.shadow.inherit = False
    return shp


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def page_head(slide, title, kicker=None):
    """统一页头：左侧蓝色竖条 + 标题 + 细分隔线"""
    rect(slide, Inches(0.62), Inches(0.52), Inches(0.06), Inches(0.42), BLUE)
    txbox(slide, Inches(0.82), Inches(0.46), Inches(11.4), Inches(0.5),
          title, size=26, bold=True)
    if kicker:
        txbox(slide, Inches(0.82), Inches(0.98), Inches(11.4), Inches(0.32),
              kicker, size=12, color=INK_3)
    rect(slide, Inches(0.62), Inches(1.36), Inches(12.1), Emu(9525), LINE)


def page_no(slide, idx):
    txbox(slide, Inches(11.9), Inches(6.92), Inches(0.8), Inches(0.3),
          f"{idx:02d}", size=11, color=INK_3, align=PP_ALIGN.RIGHT)


def bullets(slide, items, left=Inches(0.86), top=Inches(1.62),
            width=Inches(11.6), height=Inches(4.9), size=17):
    """items: [(level, text)] 或 [text]"""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for it in items:
        level, text = it if isinstance(it, tuple) else (0, it)
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = 1.35
        p.space_after = Pt(9 if level == 0 else 5)
        r = p.add_run()
        r.text = ("■ " if level == 0 else "· ") + text
        r.font.size = Pt(size if level == 0 else size - 3)
        r.font.color.rgb = INK if level == 0 else INK_2
        r.font.bold = level == 0
        r.font.name = FONT
        p.level = level


def kv_cards(slide, cards, top=Inches(1.72), h=Inches(1.55)):
    """三/四列指标卡：cards = [(label, value, desc)]"""
    n = len(cards)
    gap = Inches(0.22)
    total_w = Inches(12.1)
    cw = int((total_w - gap * (n - 1)) / n)
    for i, (label, value, desc) in enumerate(cards):
        x = Inches(0.62) + i * (cw + gap)
        rect(slide, x, top, cw, h, BLUE_LIGHT, LINE)
        txbox(slide, x + Inches(0.18), top + Inches(0.14), cw - Inches(0.36), Inches(0.3),
              label, size=12, color=INK_3)
        txbox(slide, x + Inches(0.18), top + Inches(0.44), cw - Inches(0.36), Inches(0.5),
              value, size=22, bold=True, color=BLUE)
        txbox(slide, x + Inches(0.18), top + Inches(1.0), cw - Inches(0.36), Inches(0.45),
              desc, size=11.5, color=INK_2)


def table(slide, data, left=Inches(0.62), top=Inches(1.7), width=Inches(12.1),
          col_w=None, size=13, row_h=Inches(0.42)):
    rows, cols = len(data), len(data[0])
    height = row_h * rows
    gt = slide.shapes.add_table(rows, cols, left, top, width, height).table
    if col_w:
        for i, w in enumerate(col_w):
            gt.columns[i].width = w
    for r in range(rows):
        gt.rows[r].height = row_h
        for c in range(cols):
            cell = gt.cell(r, c)
            cell.text = str(data[r][c])
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = (BLUE_LIGHT if r == 0 else (WHITE if r % 2 else RGBColor(0xFA, 0xFA, 0xFA)))
            for p in cell.text_frame.paragraphs:
                p.line_spacing = 1.0
                for run in p.runs:
                    run.font.size = Pt(size)
                    run.font.name = FONT
                    run.font.bold = (r == 0)
                    run.font.color.rgb = INK if r == 0 else INK_2
    return gt


# ==================== 幻灯片 ====================

def slide_cover(prs):
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(0.14), BLUE)
    txbox(s, Inches(1.1), Inches(1.05), Inches(11.2), Inches(0.4),
          "毕业设计（论文）开题答辩", size=15, color=INK_3)
    txbox(s, Inches(1.1), Inches(1.62), Inches(11.2), Inches(1.0),
          TITLE, size=36, bold=True)
    txbox(s, Inches(1.1), Inches(2.66), Inches(11.2), Inches(0.9),
          TITLE_EN, size=12.5, color=INK_3, line_spacing=1.35)
    rect(s, Inches(1.1), Inches(3.62), Inches(2.2), Emu(19050), BLUE)

    info = [("学　　生", f"{STUDENT}　　学号 {STUDENT_ID}"),
            ("学　　院", f"{COLLEGE}　　专业 {MAJOR}"),
            ("指导教师", ADVISOR),
            ("答辩时间", DATE)]
    y = Inches(3.95)
    for k, v in info:
        txbox(s, Inches(1.1), y, Inches(1.4), Inches(0.34), k, size=14, color=INK_3)
        txbox(s, Inches(2.5), y, Inches(9.0), Inches(0.34), v, size=14)
        y += Inches(0.46)
    page_no(s, 1)


def slide_toc(prs, idx):
    s = blank(prs)
    page_head(s, "汇报提纲")
    items = ["选题背景与意义", "国内外研究现状", "研究内容与拟解决的关键问题",
             "技术路线与系统设计", "关键方法与阶段性结果", "进度安排与预期成果"]
    y = Inches(1.78)
    for i, t in enumerate(items, 1):
        txbox(s, Inches(0.9), y, Inches(0.6), Inches(0.5), f"{i:02d}", size=20,
              bold=True, color=BLUE)
        txbox(s, Inches(1.6), y + Inches(0.04), Inches(10.5), Inches(0.5), t, size=19)
        rect(s, Inches(1.6), y + Inches(0.62), Inches(10.6), Emu(9525), LINE)
        y += Inches(0.78)
    page_no(s, idx)


def slide_background(prs, idx):
    s = blank(prs)
    page_head(s, "选题背景：校招求职的三个低效环节")
    cards = [
        ("01　重复填报", "×10", "同一份信息在多个招聘平台反复录入，字段命名与结构各不相同"),
        ("02　匹配无据", "0", "简历内容与岗位要求之间缺少可量化的匹配依据，难以判断该突出什么"),
        ("03　准备空泛", "—", "面试回答缺少与真实经历对应的事实细节与量化成果"),
    ]
    kv_cards(s, cards, top=Inches(1.72), h=Inches(1.7))
    bullets(s, [
        "大语言模型可缓解上述问题，但其幻觉与不可溯源的缺陷在求职场景被显著放大",
        "可行的技术路径是「检索增强生成 + 多 Agent 协作」：前者的知识可更新、结论可溯源，后者使多阶段任务可控可观测",
    ], top=Inches(3.72), height=Inches(2.6), size=17)
    page_no(s, idx)


def slide_related(prs, idx):
    s = blank(prs)
    page_head(s, "国内外研究现状与不足")
    data = [
        ["技术脉络", "代表性工作", "给本文的启示"],
        ["检索增强生成", "RAG[1]、DPR、C-Pack 中文嵌入[5]、Milvus[6]、HyDE", "知识可更新、结论可溯源；需解决语义鸿沟与精排开销"],
        ["多 Agent 协作", "ReAct[2]、MetaGPT[4]、多智能体综述[3][15]", "角色分工 + 交叉校验可抑制级联幻觉，但需控制节点与成本"],
        ["简历与人岗匹配", "SkillSpan[8]、职位市场分析[9]", "技能表述异构、标注稀缺；匹配需可解释而非只给分数"],
        ["生成质量评测", "RAGAS[11]、LLM-as-Judge[12]、RAG 评测综述[13]", "模型自评存在偏差，应以规则指标 + 可复现评测集为主"],
    ]
    table(s, data, top=Inches(1.66), col_w=[Inches(2.3), Inches(4.9), Inches(4.9)], size=12.5,
          row_h=Inches(0.78))
    txbox(s, Inches(0.62), Inches(5.86), Inches(12.1), Inches(0.9),
          "现有不足：单个环节研究较深入，但面向个人求职全流程的端到端系统设计与工程验证仍相对缺乏；"
          "多数工作以模型自评报告效果，缺少可复现的消融与边界分析。",
          size=13.5, color=INK_2, line_spacing=1.35)
    page_no(s, idx)


def slide_content(prs, idx):
    s = blank(prs)
    page_head(s, "研究内容（六个部分）")
    bullets(s, [
        "（1）简历解析与结构化档案：多格式文本提取、分区识别、字段来源与置信度标注，规则为主、不使用大模型改写",
        "（2）检索增强生成管道：父子分块、中文嵌入、多集合向量库、三路并行检索与融合、结构化过滤与交叉编码器精排",
        "（3）多 Agent 协作工作流：基于 LangGraph 编排规划、路由、分解、子问题并行、证据闸门、综合、写作与评审",
        "（4）项目与岗位匹配：岗位需求抽取（技术栈/软技能/年限）与项目三维打分（技术交集/年限/复杂度），生成受引用约束",
        "（5）双前端与人机交互：React 前端可视化节点状态与耗时；Chrome 扩展实现表单扫描、分区感知与一键填充",
        "（6）评测体系：可复现合成语料 + 公开真实语料，检索指标、生成质量规则化指标与消融实验方案",
    ], top=Inches(1.62), height=Inches(4.9), size=16.5)
    page_no(s, idx)


def slide_problems(prs, idx):
    s = blank(prs)
    page_head(s, "拟解决的关键问题")
    bullets(s, [
        "如何在不改写内容的前提下，保证简历字段提取的完整性与可溯源",
        "如何在个人级小规模语料上，用混合检索与轻量精排取得可用召回",
        "如何约束大模型只使用真实素材作答，避免虚构经历与数字",
        "如何让复合问题（比较、并列、多方面）的回答不遗漏要点",
        "如何在真实排版的简历（含扫描件）上保持解析可用，并客观衡量泛化差距",
    ], top=Inches(1.7), height=Inches(4.6), size=18)
    txbox(s, Inches(0.86), Inches(5.95), Inches(11.6), Inches(0.8),
          "对应策略：规则解析 + 来源标注　｜　三路并行检索 + 融合投票　｜　引用约束 + 规则校验　｜　"
          "分解与证据闸门回环　｜　整块文本结构化 + OCR 兜底 + 双语料评测",
          size=12.5, color=INK_2, line_spacing=1.35)
    page_no(s, idx)


def slide_arch(prs, idx):
    s = blank(prs)
    page_head(s, "技术路线：分层架构")
    layers = [
        ("接口层", "HTTP 接口（简历/检索/问答/对练/匹配/表单），健康检查与系统信息"),
        ("业务层", "自我介绍 · 面试问答 · 岗位匹配 · 表单映射"),
        ("编排层", "LangGraph 多 Agent 工作流：规划 → 路由 → (分解/检索) → 写作 → 评审 → 条件修订"),
        ("检索层", "父子分块 · 中文嵌入 · 三路并行检索 · 融合投票 · 交叉编码器精排"),
        ("解析层", "PyMuPDF / python-docx 提取 · 整块文本结构化 · 分区识别 · 字段抽取 · OCR 兜底"),
    ]
    y = Inches(1.7)
    for i, (name, desc) in enumerate(layers):
        rect(s, Inches(0.62), y, Inches(2.1), Inches(0.82), BLUE_LIGHT, LINE)
        txbox(s, Inches(0.62), y + Inches(0.24), Inches(2.1), Inches(0.36),
              name, size=15, bold=True, align=PP_ALIGN.CENTER)
        rect(s, Inches(2.86), y, Inches(9.85), Inches(0.82), WHITE, LINE)
        txbox(s, Inches(3.06), y + Inches(0.1), Inches(9.5), Inches(0.66),
              desc, size=13, color=INK_2, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.25)
        y += Inches(0.96)
    page_no(s, idx)


def slide_graph(prs, idx):
    s = blank(prs)
    page_head(s, "多 Agent 工作流：9 节点，含分解与证据回环")
    nodes = ["Planner\n动态规划", "Router\n问题路由", "Decompose\n复合问题拆解",
             "SubAnswer\n子问题并行", "EvidenceGate\n证据闸门", "Synthesize\n整合总答",
             "ParallelRetrieval\n三路并行", "Writer\nSTAR 写作", "ParallelReview\n三路评审"]
    cols, rows = 5, 2
    bw, bh = Inches(2.3), Inches(1.05)
    gap_x, gap_y = Inches(0.16), Inches(0.28)
    for i, n in enumerate(nodes):
        r, c = divmod(i, cols)
        x = Inches(0.62) + c * (bw + gap_x)
        y = Inches(1.66) + r * (bh + gap_y)
        is_blue = n.startswith(("Decompose", "SubAnswer", "EvidenceGate", "Synthesize"))
        rect(s, x, y, bw, bh, (BLUE if is_blue else WHITE), (None if is_blue else LINE))
        txbox(s, x + Inches(0.08), y + Inches(0.12), bw - Inches(0.16), bh - Inches(0.2),
              n, size=12.5, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
              color=(WHITE if is_blue else INK), line_spacing=1.25)
    txbox(s, Inches(0.62), Inches(4.42), Inches(12.1), Inches(0.4),
          "蓝色为复合问题专用链路：判断为复合问题才启用，非复合问题走原链路，避免为复杂而复杂。",
          size=12.5, color=INK_2)
    bullets(s, [
        "证据闸门：子问题证据不足时生成定向补充查询，回环一轮再作答（Self-RAG 式）",
        "评审不通过则回到写作节点重写；单节点失败只降级不阻断，节点级耗时全程可观测",
    ], top=Inches(4.86), height=Inches(1.7), size=14)
    page_no(s, idx)


def slide_method(prs, idx):
    s = blank(prs)
    page_head(s, "关键方法与设计取舍")
    data = [
        ["设计点", "做法", "为什么这样取舍"],
        ["解析保真", "规则抽取 + 来源行号 + 置信度，不调用大模型改写", "求职材料对事实准确性要求高，不可溯源即不可用"],
        ["混合检索", "关键词/语义/知识图谱三路并行 + 融合投票 + 精排", "单路检索在专有名词或语义泛化上各有短板"],
        ["生成约束", "引用约束 + 数字原样引用 + 规则化校验", "把「不编造」变成可检测的约束，而非依赖模型自觉"],
        ["分解与回环", "复合问题拆解 → 子问题并行 → 证据闸门 → 综合", "让回答覆盖度不依赖单次生成是否想到全部要点"],
        ["可复现评测", "程序化语料 + 独立评测库 + 规则指标 + 消融", "避免模型自评的循环论证，结论可被复核"],
    ]
    table(s, data, top=Inches(1.66), col_w=[Inches(2.1), Inches(5.0), Inches(5.0)], size=12.5,
          row_h=Inches(0.78))
    page_no(s, idx)


def slide_results(prs, idx):
    s = blank(prs)
    page_head(s, "阶段性结果（已完成的可复现评测）")
    data = [
        ["实验", "设置", "主要结果"],
        ["简历字段提取", "12 份规范合成简历，对照种子真值", "字段级准确率 100%（技能 P/R/F1 均为 1.000）"],
        ["解析鲁棒性", "48 份公开真实语料（CC0/MIT，含 8 份扫描件）", "文本提取 100%，结构化 83.3%（余为越南语简历）"],
        ["检索质量与消融", "223 道标注问题，六模式消融", "Recall@5 0.876，MRR 0.780，nDCG@5 0.809"],
        ["生成质量三档对照", "单次调用 / 快速 / 完整工作流", "快速档 6/6 有效且 STAR 100%，约 12 秒"],
        ["复合问题分解", "5 道多方面问题，规则计算方面覆盖率", "覆盖率 93.3% → 100%，与全文直送持平"],
        ["网申表单填充", "85 个字段、5 类站点夹具", "覆盖率 88.2%，下拉别名 10/10，空值不编造 5/5"],
    ]
    table(s, data, top=Inches(1.66), col_w=[Inches(2.5), Inches(4.5), Inches(5.1)], size=12,
          row_h=Inches(0.66))
    page_no(s, idx)


def slide_plan(prs, idx):
    s = blank(prs)
    page_head(s, "进度安排")
    data = [
        ["阶段", "时间", "主要工作"],
        ["选题与调研", "2026.11.07 — 2026.12.04", "任务下达、需求调研、选题论证、技术路线确定"],
        ["文献与开题", "2026.12.05 — 2026.12.25", "文献检索与综述、开题报告、资料库建设"],
        ["开题答辩", "2026.12.29", "参加开题答辩，按意见调整研究重点"],
        ["系统实现", "2026.12.30 — 2027.03.31", "框架与核心链路：解析、检索、多 Agent、问答"],
        ["功能完善与实验", "2027.04.01 — 2027.04.30", "全部功能、论文初稿、评测集与消融实验"],
        ["中期检查", "2027.04.30 前", "接受中期检查，按意见完善实现与写作"],
        ["定稿与答辩", "2027.05.01 — 2027.05.15", "论文终稿、查重与格式审查、答辩与作品演示"],
    ]
    table(s, data, top=Inches(1.62), col_w=[Inches(2.6), Inches(4.0), Inches(5.5)], size=12,
          row_h=Inches(0.6))
    page_no(s, idx)


def slide_expected(prs, idx):
    s = blank(prs)
    page_head(s, "预期成果")
    cards = [
        ("软件系统", "1 套", "Web 前端 + 浏览器扩展 + 后端服务，可完整演示求职全链路"),
        ("毕业设计论文", "1 篇", "含系统设计、实现与六组可复现实验分析"),
        ("评测与工具", "1 套", "可复现评测脚本、消融方案与评测数据"),
        ("工程记录", "1 份", "缺陷与修复记录、边界与降级策略说明"),
    ]
    kv_cards(s, cards, top=Inches(1.76), h=Inches(1.9))
    bullets(s, [
        "预期贡献：形成「规则解析保真 + 混合检索 + 多 Agent 约束 + 可复现评测」的个人化智能应用工程范式",
        "同时如实报告负面结果与适用边界（如部分检索增强在小语料下收益趋零、OCR 的时延代价）",
    ], top=Inches(3.92), height=Inches(2.3), size=16)
    page_no(s, idx)


def slide_refs(prs, idx):
    s = blank(prs)
    page_head(s, "主要参考文献（节选）")
    refs = [
        "[1] LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//NeurIPS, 2020.",
        "[2] YAO S, ZHAO J, YU D, et al. ReAct: synergizing reasoning and acting in language models[C]//ICLR, 2023.",
        "[3] GUO T, CHEN X, WANG Y, et al. Large language model based multi-agents: a survey[J]. arXiv:2402.01680, 2024.",
        "[5] XIAO S, LIU Z, ZHANG P, et al. C-Pack: packed resources for general Chinese embeddings[C]//SIGIR, 2023.",
        "[6] WANG J, YI X, GUO R, et al. Milvus: a purpose-built vector data management system[C]//SIGMOD, 2021.",
        "[8] ZHANG M, JENSEN K N, SONNIKS S D, et al. SkillSpan: hard and soft skill extraction[J]. NAACL, 2022.",
        "[15] XI Z, CHEN W, GUO X, et al. 基于大语言模型的智能体: 发展与未来展望[J]. 中国科学: 信息科学, 2025, 56(2): 485.",
        "[18] 全国网络安全标准化技术委员会. 网络安全技术 生成式人工智能服务安全基本要求: GB/T 45654—2025[S]. 2025.",
    ]
    box = s.shapes.add_textbox(Inches(0.86), Inches(1.6), Inches(11.9), Inches(4.9))
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for r in refs:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.line_spacing = 1.3
        p.space_after = Pt(8)
        run = p.add_run()
        run.text = r
        run.font.size = Pt(11.5)
        run.font.color.rgb = INK_2
        run.font.name = FONT
    txbox(s, Inches(0.86), Inches(6.5), Inches(11.6), Inches(0.4),
          "开题报告共著录 19 篇文献（外文 14 篇、中文 5 篇），正文编号与文献表通过交叉引用域联动。",
          size=11.5, color=INK_3)
    page_no(s, idx)


def slide_end(prs, idx):
    s = blank(prs)
    rect(s, Inches(0), Inches(0), W, Inches(0.14), BLUE)
    txbox(s, Inches(0.9), Inches(2.7), Inches(11.5), Inches(0.9),
          "请各位老师批评指正", size=40, bold=True, align=PP_ALIGN.CENTER)
    txbox(s, Inches(0.9), Inches(3.72), Inches(11.5), Inches(0.5),
          "感谢聆听　·　Q & A", size=17, color=INK_3, align=PP_ALIGN.CENTER)
    rect(s, Inches(5.55), Inches(4.55), Inches(2.2), Emu(28575), BLUE)
    txbox(s, Inches(0.9), Inches(4.9), Inches(11.5), Inches(0.4),
          f"{STUDENT}　·　{MAJOR}　·　{COLLEGE}", size=13, color=INK_3, align=PP_ALIGN.CENTER)
    page_no(s, idx)


def build(out_path: Path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    slide_cover(prs)
    slide_toc(prs, 2)
    slide_background(prs, 3)
    slide_related(prs, 4)
    slide_content(prs, 5)
    slide_problems(prs, 6)
    slide_arch(prs, 7)
    slide_graph(prs, 8)
    slide_method(prs, 9)
    slide_results(prs, 10)
    slide_plan(prs, 11)
    slide_expected(prs, 12)
    slide_refs(prs, 13)
    slide_end(prs, 14)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    print(f"已生成: {out_path}")
    print(f"共 {len(prs.slides.__iter__.__self__._sldIdLst)} 页")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("开题答辩.pptx")
    build(target)
