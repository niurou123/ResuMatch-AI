# -*- coding: utf-8 -*-
"""简历解析器回归测试 — 覆盖 BUG_LOG 案例 30/31 修复点

对应缺陷：
1. markdown 子标题（### 项目名）在分区识别时被当作分区标题丢弃
2. 项目块未按 ### 标题切分，多项目被合并为一个
3. 4 字中文项目名（统一网关/特征平台）被 len<5 过滤掉
4. "关键成就/核心成果"等标题未被识别为成果分区
5. 教育行按整体赋值给 school，专业被关键词表截断
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rag.parser import ResumeParser  # noqa: E402

MD_RESUME = """# 张三的简历

求职方向: 后端开发

## 技能
Python, FastAPI, MySQL

## 项目经验
### 电商订单中台
角色: 后端负责人
技术栈: FastAPI, MySQL
描述: 处理日均10万订单的订单中台
关键成果:
- 订单接口 P99 延迟 800ms→120ms

### 统一网关
角色: 架构设计
技术栈: Go, Nginx
描述: 统一流量入口
关键成果:
- 网关转发延迟降低 40%

## 关键成就
- 电商订单中台：订单接口 P99 延迟 800ms→120ms

## 教育背景
华南理工大学 计算机技术 硕士 2024-2027
郑州大学 软件工程 学士 2020-2024
"""


@pytest.fixture()
def parsed(tmp_path):
    fp = tmp_path / "resume_test.md"
    fp.write_text(MD_RESUME, encoding="utf-8")
    return ResumeParser().parse(str(fp))


def test_md_subheading_project_name_not_lost(parsed):
    """### 项目名 必须成为项目名，而不是被当作标题丢弃"""
    names = [p.get("name", "") for p in parsed.projects]
    assert "电商订单中台" in names, f"首个项目名丢失，实际={names}"


def test_projects_split_by_md_heading(parsed):
    """两个 ### 项目应被切成两个项目块"""
    assert len(parsed.projects) == 2, [p.get("name") for p in parsed.projects]


def test_short_chinese_project_name_kept(parsed):
    """4 字项目名（统一网关）不应被长度阈值过滤"""
    names = [p.get("name", "") for p in parsed.projects]
    assert any("统一网关" in n for n in names), names


def test_project_role_and_tech(parsed):
    proj = next(p for p in parsed.projects if "电商" in p.get("name", ""))
    assert "后端负责人" in proj.get("role", "")
    assert {"FastAPI", "MySQL"} <= set(proj.get("tech_stack") or [])


def test_achievements_section_recognized(parsed):
    """关键成就 必须被识别为 achievements 分区且有内容"""
    assert "achievements" in parsed.sections
    assert len(parsed.achievements) >= 1


def test_education_fields_split(parsed):
    """学校/专业/学位应正确拆分，专业不得被关键词表截断"""
    assert len(parsed.education) == 2
    first = parsed.education[0]
    assert "华南理工大学" in first.get("school", ""), first
    assert "计算机技术" in first.get("major", ""), first
    assert "硕士" in first.get("degree", ""), first
    assert "2024-2027" in first.get("time", ""), first


# ===== BUG_LOG 案例 33/34：整块文本结构化 + OCR 兜底 =====
def test_normalize_blob_text_splits_inline_headings():
    """PDF 提取出的整块文本，应把被空格包夹的英文分区标题单独成段"""
    parser = ResumeParser()
    blob = "HR ADMINISTRATOR       Summary     Dedicated manager with 15 years.   Education   BSc in HR"
    out = parser._normalize_blob_text(blob)
    lines = [l.strip() for l in out.split("\n") if l.strip()]
    assert "Summary" in lines, lines
    assert "Education" in lines, lines


def test_ocr_engine_is_lazy_and_switchable(monkeypatch):
    """OCR 引擎必须惰性初始化，且可通过 OCR_ENABLED 关闭（纯文本不应付出模型加载开销）"""
    import src.rag.parser as P
    monkeypatch.setattr(P, "OCR_ENABLED", False)
    parser = ResumeParser()
    assert parser._get_ocr_engine() is None