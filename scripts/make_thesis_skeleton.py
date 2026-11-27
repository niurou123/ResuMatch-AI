# -*- coding: utf-8 -*-
"""生成毕业设计论文骨架（格式严格对齐 7理工类毕业设计模板.doc）

为什么从零构建而不是直接改模板文件：
    模板里混有大量示例正文与占位符，就地改写容易破坏分节与样式；而正文所需的
    格式规则（页边距、字体字号、行距、缩进、标题层级）已从模板中逐条提取，
    从零构建反而能保证每一段都落在规范上，且可被 check_thesis_format.py 校验通过。

产物：一份带结构、带写作提示、可直接填内容的 .docx
    - 封面 / 郑重声明 / 摘要 / Abstract / 目录（TOC 域）/ 正文六章 / 参考文献 / 致谢 / 附录
    - 正文每节留「本节待写」提示，避免模板占位符残留
用法：
    python scripts/make_thesis_skeleton.py "输出路径.docx"
"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

SONG = "宋体"
HEI = "黑体"
LI = "隶书"

# 官方模板规范
BODY_SIZE = 12.0        # 小四
H1_SIZE = 14.0          # 四号
LINE = 1.25             # 1.25 倍行距
INDENT = Pt(24)         # 首行缩进 2 字符


def set_run_font(run, name=SONG, size=BODY_SIZE, bold=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = None
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    rFonts.set(qn("w:eastAsia"), name)


def setup_page(doc):
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin = s.bottom_margin = Cm(2.5)
    s.left_margin = s.right_margin = Cm(2.5)
    s.header_distance = Cm(1.5)
    s.footer_distance = Cm(1.75)


def setup_styles(doc):
    """把 Normal / Heading 1~3 改成模板规定的格式"""
    st = doc.styles["Normal"]
    st.font.name = SONG
    st.font.size = Pt(BODY_SIZE)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), SONG)
    pf = st.paragraph_format
    pf.line_spacing = LINE
    pf.first_line_indent = INDENT
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for name, size in (("Heading 1", H1_SIZE), ("Heading 2", BODY_SIZE), ("Heading 3", BODY_SIZE)):
        s = doc.styles[name]
        s.font.name = SONG
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = None
        if s.element.rPr is None:
            s.element.get_or_add_rPr()
        rF = s.element.rPr.find(qn("w:rFonts"))
        if rF is None:
            rF = OxmlElement("w:rFonts")
            s.element.rPr.append(rF)
        rF.set(qn("w:ascii"), SONG)
        rF.set(qn("w:hAnsi"), SONG)
        rF.set(qn("w:eastAsia"), SONG)
        pf = s.paragraph_format
        pf.line_spacing = LINE
        pf.space_before = Pt(7.8 if name == "Heading 1" else 0)
        pf.space_after = Pt(7.8 if name == "Heading 1" else 0)
        pf.first_line_indent = Pt(0) if name == "Heading 1" else INDENT
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.keep_with_next = True


def p(doc, text="", size=BODY_SIZE, bold=False, font=SONG,
      align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=INDENT, before=0, after=0, line=LINE):
    par = doc.add_paragraph()
    pf = par.paragraph_format
    pf.alignment = align
    pf.first_line_indent = indent
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    if text:
        r = par.add_run(text)
        set_run_font(r, font, size, bold)
    return par


def head(doc, text, level=1, center=False):
    h = doc.add_paragraph(style=f"Heading {level}")
    if center:
        h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run(text)
    set_run_font(r, SONG, H1_SIZE if level == 1 else BODY_SIZE, True)
    return h


def page_break(doc):
    par = doc.add_paragraph()
    par.add_run().add_break(WD_BREAK.PAGE)


def add_toc(doc):
    """插入 TOC 域（Word 中右键“更新域”即可生成目录）"""
    par = doc.add_paragraph()
    r = par.add_run()
    fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "begin"); fld.set(qn("w:dirty"), "true")
    r._element.append(fld)
    r2 = par.add_run()
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = r'TOC \o "1-3" \h \z \u'
    r2._element.append(instr)
    r3 = par.add_run()
    sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate")
    r3._element.append(sep)
    r4 = par.add_run("（在 Word 中右键此处选择“更新域”生成目录）")
    set_run_font(r4, SONG, BODY_SIZE)
    r5 = par.add_run()
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    r5._element.append(end)


# ==================== 各部分内容 ====================

TITLE_CN = "基于LangGraph的多Agent协作AI求职面试系统"
TITLE_EN = "Design and Implementation of a LangGraph-based Multi-Agent AI Job-Seeking Interview System"
INFO = {
    "学生姓名": "刘汪洋", "学号": "235703240", "二级学院名称": "媒体工程学院",
    "专业": "人工智能", "指导教师": "张丽", "职称": "副教授",
}

ABSTRACT_CN = (
    "针对校园招聘场景中简历信息易失真、网申表单重复填报耗时、面试回答缺乏真实经历支撑等问题，"
    "本文设计并实现了一个基于 LangGraph 的多 Agent 协作 AI 求职面试系统。系统采用纯规则解析路线"
    "完成简历结构化提取并为每个字段标注来源与置信度；构建关键词、语义与知识图谱三路并行检索并做"
    "融合投票，引入假设文档检索、结构化过滤、交叉编码器精排、父子分块与技能知识图谱等增强技术；"
    "设计由动态规划、问题路由、并行检索、STAR 写作、并行评审与条件修订构成的多 Agent 工作流，"
    "约束大模型在真实素材范围内生成回答；同时实现浏览器扩展用于网申页面表单扫描与一键填充。"
    "在可复现评测集上完成了字段提取、检索质量、生成质量、多 Agent 有效性与表单填充覆盖率五组实验。"
    "结果表明：系统在规范排版简历上的字段提取与元数据还原准确，检索与生成指标达到可用水平，"
    "多 Agent 工作流的价值主要体现在过程可控与可观测，而端到端延迟相应增加。"
)
KEYWORDS_CN = "检索增强生成；多 Agent 协作；LangGraph；简历解析；求职面试系统"

ABSTRACT_EN = (
    "To address the problems of information distortion in resume extraction, time-consuming repeated "
    "filling of online application forms, and interview answers lacking support from real experience in "
    "campus recruitment, this thesis designs and implements a LangGraph-based multi-agent AI job-seeking "
    "interview system. The system adopts a rule-based parsing pipeline to structure resumes and annotates "
    "the source and confidence of every field. It builds three parallel retrieval channels (keyword, "
    "semantic and knowledge graph) with fusion voting, and introduces hypothetical document retrieval, "
    "structured filtering, cross-encoder re-ranking, parent-child chunking and a skill knowledge graph. "
    "A multi-agent workflow composed of dynamic planning, question routing, parallel retrieval, STAR "
    "writing, parallel review and conditional revision constrains the large language model to generate "
    "answers grounded in real materials. A browser extension is implemented for form scanning and "
    "one-click filling. Five reproducible experiments cover field extraction accuracy, retrieval quality, "
    "generation quality, multi-agent effectiveness and form-filling coverage. Results show that extraction "
    "and metadata recovery are accurate on well-formatted resumes, retrieval and generation reach a usable "
    "level, and the value of the multi-agent workflow lies mainly in controllability and observability, "
    "at the cost of longer end-to-end latency."
)
KEYWORDS_EN = "Retrieval-Augmented Generation; Multi-Agent Collaboration; LangGraph; Resume Parsing; Job-Seeking Interview System"

OUTLINE = [
    ("1 绪论", [
        ("1.1 研究背景与意义", "说明校园招聘场景下的三类痛点，以及引入大语言模型与检索增强生成的必要性。"),
        ("1.2 国内外研究现状", "概括检索增强生成、多 Agent 协作、简历解析与人岗匹配、生成质量评测四条脉络。（材料可直接取自文献综述）"),
        ("1.3 研究内容与论文组织结构", "列出本文四项主要工作，并给出各章安排。"),
        ("1.4 本章小结", "一段话收束。"),
    ]),
    ("2 相关技术基础", [
        ("2.1 检索增强生成技术", "介绍 RAG 基本框架、稠密检索与稀疏检索、假设文档检索与交叉编码器精排。"),
        ("2.2 多 Agent 协作与工作流编排", "介绍 LangGraph 状态图模型、条件边与状态传递机制。"),
        ("2.3 文本嵌入与向量检索", "介绍中文嵌入模型与向量库的索引与检索方式。"),
        ("2.4 本章小结", "一段话收束。"),
    ]),
    ("3 系统需求分析与总体设计", [
        ("3.1 需求分析", "功能性需求（解析、档案、填充、匹配、问答、对练）与非功能性需求（可靠性、隐私、可维护性）。"),
        ("3.2 系统总体架构", "分层架构图：解析层、检索层、编排层、业务层、接口层、双前端。"),
        ("3.3 功能模块划分", "逐模块说明职责与相互调用关系。"),
        ("3.4 数据结构与存储设计", "结构化档案、向量集合、会话与缓存的设计。"),
        ("3.5 本章小结", "一段话收束。"),
    ]),
    ("4 关键模块设计与实现", [
        ("4.1 简历解析与结构化档案模块", "分区识别规则、字段抽取、来源标注与置信度；对应字段提取准确率实验。"),
        ("4.2 检索增强生成管道", "父子分块、向量化、三路并行检索、融合投票、自查询过滤与精排。"),
        ("4.3 多 Agent 协作工作流", "五个节点的职责、状态字段、条件边与降级退路。"),
        ("4.4 项目与岗位匹配模块", "需求抽取与三维度打分，以及针对性内容生成。"),
        ("4.5 网申表单智能填充", "表单扫描、分区感知、别名匹配与受控组件写入。"),
        ("4.6 本章小结", "一段话收束。"),
    ]),
    ("5 系统测试与实验分析", [
        ("5.1 测试环境与评测集", "硬件软件环境；匿名简历与标注问题的构造方式、可复现性设计。"),
        ("5.2 字段提取准确率评测", "按技能、项目、教育、成果四类字段统计命中率。"),
        ("5.3 检索质量与消融实验", "Recall@k、MRR、nDCG@k 指标与各增强技术的边际贡献。"),
        ("5.4 生成质量与多 Agent 有效性对比", "STAR 完整率、数字可回溯率，以及全量／快速／单 Agent 三档对照。"),
        ("5.5 表单填充覆盖率评测", "分站点统计字段覆盖率与空值不编造率。"),
        ("5.6 本章小结", "归纳实验结论，正面说明多 Agent 的收益与代价。"),
    ]),
    ("6 总结与展望", [
        ("6.1 工作总结", "概述完成的工作与主要结论。"),
        ("6.2 不足与展望", "说明规范排版之外的复杂简历、检索增强技术的适用边界、延迟优化方向。"),
    ]),
]

ACK = [
    "本论文的完成离不开导师张丽副教授的悉心指导。从选题论证、方案设计到系统实现与论文撰写，"
    "张老师多次提出针对性意见，帮助我厘清研究思路、修正技术路线，并在关键节点给予督促与鼓励。"
    "谨向张老师致以诚挚的谢意。",
    "感谢媒体工程学院各位老师在课程教学与开题、中期检查环节给予的指导，"
    "感谢实验室提供的设备与场地支持；感谢同学在系统联调、测试数据整理与答辩材料准备过程中给予的帮助。",
    "感谢家人在学习期间给予的理解与支持。最后，感谢各位评阅老师在百忙之中审阅本文并提出宝贵意见。",
]

APPENDIX = [
    "附录A 系统主要接口一览。系统后端按功能分为简历与档案、检索与问答、面试对练、岗位匹配与表单填充五组接口，"
    "分别提供简历上传与档案读写、面试问答与流式输出、对练会话与问题生成、匹配分析与针对性内容生成、表单映射等服务，"
    "并通过健康检查与系统信息接口对外暴露运行状态。",
    "附录B 评测集说明。评测集以程序化方式生成，包含 12 份匿名简历与 355 道标注问题，其中 223 道标注了检索目标；"
    "生成脚本幂等，可随时重建，评测使用独立向量库与独立进程，不影响系统运行数据。",
    "附录C 实验数据与代码。四组实验的原始结果以 JSON 形式保存在项目 data/eval 目录，"
    "字段提取、检索质量、生成质量与表单填充的评测脚本分别位于 scripts 目录，可复现对应指标。",
]

REFERENCES = [    "[1]LEWIS P, PEREZ E, PIKTUS A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks[C]//Advances in Neural Information Processing Systems 33. Red Hook: Curran Associates, 2020: 9459-9474.",
    "[2]GAO L, MA X, LIN J, et al. Precise zero-shot dense retrieval without relevance labels[C]//Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics. Toronto: ACL, 2023: 1762-1777.",
    "[3]KARPUKHIN V, OGUZ B, MIN S, et al. Dense passage retrieval for open-domain question answering[C]//Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing. Stroudsburg: ACL, 2020: 6769-6781.",
    "[4]REIMERS N, GUREVYCH I. Sentence-BERT: sentence embeddings using Siamese BERT-networks[C]//Proceedings of EMNLP-IJCNLP 2019. Stroudsburg: ACL, 2019: 3980-3990.",
    "[5]XIAO S, LIU Z, ZHANG P, et al. C-Pack: packed resources for general Chinese embeddings[C]//Proceedings of the 47th International ACM SIGIR Conference. New York: ACM, 2024: 641-649.",
    "[6]MUENNIGHOFF N, TAZI N, MAGNE L, et al. MTEB: massive text embedding benchmark[C]//Proceedings of the 17th Conference of the European Chapter of the ACL. Stroudsburg: ACL, 2023: 2014-2037.",
    "[7]ROBERTSON S, ZARAGOZA H. The probabilistic relevance framework: BM25 and beyond[J]. Foundations and Trends in Information Retrieval, 2009, 4(1-2): 1-174.",
    "[8]WANG J, YI X, GUO R, et al. Milvus: a purpose-built vector data management system[C]//Proceedings of the 2021 International Conference on Management of Data. New York: ACM, 2021: 2614-2627.",
    "[9]YAO S, ZHAO J, YU D, et al. ReAct: synergizing reasoning and acting in language models[C]//Proceedings of the 11th International Conference on Learning Representations. Kigali: ICLR, 2023.",
    "[10]HONG S, ZHUGE M, CHEN J, et al. MetaGPT: meta programming for a multi-agent collaborative framework[C]//Proceedings of the 12th International Conference on Learning Representations. Vienna: ICLR, 2024.",
    "[11]GUO T, CHEN X, WANG Y, et al. Large language model based multi-agents: a survey of progress and challenges[C]//Proceedings of the 33rd International Joint Conference on Artificial Intelligence. Jeju: IJCAI, 2024: 8048-8057.",
    "[12]ZHENG L, CHIANG W L, SHENG Y, et al. Judging LLM-as-a-judge with MT-Bench and Chatbot Arena[C]//Advances in Neural Information Processing Systems 36. Red Hook: Curran Associates, 2023: 46595-46623.",
    "[13]LIU Y, ITER D, XU Y, et al. G-Eval: NLG evaluation using GPT-4 with better human alignment[C]//Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing. Stroudsburg: ACL, 2023: 2511-2522.",
    "[14]ES S, JAMES J, ESPINOSA-ANKE L, et al. RAGAS: automated evaluation of retrieval augmented generation[C]//Proceedings of EACL 2024: System Demonstrations. Stroudsburg: ACL, 2024: 150-158.",
    "[15]YU H, GAN A, ZHANG K, et al. Evaluation of retrieval-augmented generation: a survey[C]//Communications in Computer and Information Science. Singapore: Springer, 2025: 102-120.",
    "[16]ZHANG M, JENSEN K N, SONNIKS S D, et al. SkillSpan: hard and soft skill extraction from English job postings[C]//Proceedings of NAACL-HLT 2022. Stroudsburg: ACL, 2022: 4962-4984.",
    "[17]SENGER E, ZHANG M, VAN DER GOOT R, et al. Deep learning-based computational job market analysis: a survey on skill extraction and classification from job postings[C]//Proceedings of the First Workshop on NLP for Human Resources. Stroudsburg: ACL, 2024: 1-15.",
    "[18]WU L, QIU Z, ZHENG Z, et al. Exploring large language model for graph data understanding in online job recommendations[C]//Proceedings of the AAAI Conference on Artificial Intelligence, 2024, 38(8): 9178-9186.",
    "[19]DENG X, GU Y, ZHENG B, et al. Mind2Web: towards a generalist agent for the web[C]//Advances in Neural Information Processing Systems 36. Red Hook: Curran Associates, 2023: 28091-28114.",
    "[20]GRESHAKE K, ABDELNABI S, MISHRA S, et al. Not what you have signed up for: compromising real-world LLM-integrated applications with indirect prompt injection[C]//Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security. New York: ACM, 2023: 79-90.",
    "[21]周志华. 机器学习[M]. 北京: 清华大学出版社, 2016.",
    "[22]国家市场监督管理总局, 国家标准化管理委员会. 信息安全技术 个人信息安全规范: GB/T 35273—2020[S]. 北京: 中国标准出版社, 2020.",
    "[23]XI Z, CHEN W, GUO X, et al. 基于大语言模型的智能体: 发展与未来展望[J]. 中国科学: 信息科学, 2025, 56(2): 485.",
    "[24]李航. 统计学习方法: 第2版[M]. 北京: 清华大学出版社, 2019.",
    "[25]王昊奋, 漆桂林, 陈华钧. 知识图谱: 方法、实践与应用[M]. 北京: 电子工业出版社, 2019.",
    "[26]全国网络安全标准化技术委员会. 网络安全技术 生成式人工智能服务安全基本要求: GB/T 45654—2025[S]. 北京: 中国标准出版社, 2025.",
    "[27]国家市场监督管理总局, 国家标准化管理委员会. 信息技术 人工智能 术语: GB/T 41867—2022[S]. 北京: 中国标准出版社, 2022.",
]


def load_content():
    """读取正文内容源 scripts/thesis_content.json；不存在则返回 None（回退到提示骨架）"""
    import json
    cp = Path(__file__).resolve().parent / "thesis_content.json"
    if not cp.exists():
        return None
    try:
        return json.loads(cp.read_text(encoding="utf-8"))
    except Exception as ex:
        print(f"[warn] 正文内容源解析失败，回退提示骨架: {ex}")
        return None


def build(out_path: Path):
    doc = Document()
    setup_page(doc)
    setup_styles(doc)

    # ---------- 封面 ----------
    for _ in range(2):
        p(doc, "", indent=Pt(0))
    p(doc, "毕业设计", 36, True, LI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), line=1.0)
    p(doc, "（2027 届）", 18, False, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), before=6)
    for _ in range(2):
        p(doc, "", indent=Pt(0))
    p(doc, TITLE_CN, 22, True, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), before=6, after=6)
    p(doc, TITLE_EN, 12, False, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), before=6, after=18)

    tbl = doc.add_table(rows=len(INFO), cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (k, v) in enumerate(INFO.items()):
        c0, c1 = tbl.rows[i].cells
        c0.width, c1.width = Cm(5.0), Cm(6.5)
        r0 = c0.paragraphs[0].add_run(k + "：")
        set_run_font(r0, SONG, 14)
        r1 = c1.paragraphs[0].add_run(v)
        set_run_font(r1, SONG, 14)
        for c in (c0, c1):
            c.paragraphs[0].paragraph_format.first_line_indent = Pt(0)
            c.paragraphs[0].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for _ in range(2):
        p(doc, "", indent=Pt(0))
    p(doc, "2026 年 11 月", 14, False, SONG, WD_ALIGN_PARAGRAPH.CENTER, Pt(0))
    page_break(doc)

    # ---------- 郑重声明 ----------
    p(doc, "郑 重 声 明", 18, True, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), after=18)
    p(doc, f"我谨在此郑重声明：本人所写的毕业设计《{TITLE_CN}》均系本人独立完成，"
           "没有任何抄袭、伪造、篡改、代写、买卖等学术不端行为，文中引用他人成果之处均已标注来源。", line=1.75)
    p(doc, "", indent=Pt(0))
    p(doc, "承诺人（签名）：刘汪洋", 12, False, SONG, WD_ALIGN_PARAGRAPH.RIGHT, Pt(0))
    p(doc, "2026 年 11 月    日", 12, False, SONG, WD_ALIGN_PARAGRAPH.RIGHT, Pt(0))
    page_break(doc)

    # ---------- 摘要 ----------
    p(doc, "摘  要", 18, True, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), after=12)
    p(doc, ABSTRACT_CN)
    p(doc, "关键词：" + KEYWORDS_CN, bold=True)
    page_break(doc)

    # ---------- Abstract ----------
    p(doc, "Abstract", 18, True, "Times New Roman", WD_ALIGN_PARAGRAPH.CENTER, Pt(0), after=12)
    p(doc, ABSTRACT_EN)
    p(doc, "Keywords: " + KEYWORDS_EN, bold=True)
    page_break(doc)

    # ---------- 目录 ----------
    p(doc, "目  录", 18, True, HEI, WD_ALIGN_PARAGRAPH.CENTER, Pt(0), after=12)
    add_toc(doc)
    page_break(doc)

    # ---------- 正文 ----------
    content = load_content()
    if content:
        for ch in content["chapters"]:
            head(doc, ch["title"], 1)
            for sec in ch["sections"]:
                level = 2 if sec["title"].count(".") == 1 else 3
                head(doc, sec["title"], level)
                for para in sec.get("paras", []):
                    p(doc, para)
            page_break(doc)
    else:
        # 回退：没有内容源时输出带写作提示的结构
        for ch_title, sections in OUTLINE:
            head(doc, ch_title, 1)
            for sec_title, hint in sections:
                level = 2 if sec_title.count(".") == 1 else 3
                head(doc, sec_title, level)
                p(doc, "【本节待写】" + hint)
            page_break(doc)

    # ---------- 参考文献 ----------
    head(doc, "参考文献", 1, center=True)
    for ref in REFERENCES:
        p(doc, ref, indent=Pt(0))

    # ---------- 致谢 ----------
    page_break(doc)
    head(doc, "致谢", 1, center=True)
    for para in ACK:
        p(doc, para)

    # ---------- 附录 ----------
    page_break(doc)
    head(doc, "附录", 1, center=True)
    for para in APPENDIX:
        p(doc, para)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"已生成: {out_path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("毕业设计论文-骨架.docx")
    build(target)
