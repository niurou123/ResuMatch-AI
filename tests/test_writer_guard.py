# -*- coding: utf-8 -*-
"""写作节点的残答防护（BUG_LOG 案例 32）

覆盖 `_looks_truncated` 的判定边界：空串、极短残答、无结构长文本、
以及结构完整且长度达标的正常回答。
"""
from src.agents.writer import MIN_ANSWER_CHARS, _looks_truncated

STAR_OK = (
    "**情境（Situation）**：我在电商订单中台项目中负责后端负责人，团队 5 人。"
    "**任务（Task）**：需要把下单接口在峰值期的延迟从 800ms 降到 200ms 以内。"
    "**行动（Action）**：采用异步削峰与幂等设计，引入 Celery 任务队列，"
    "并对热点商品做本地缓存，同时补齐分布式事务的回滚路径。"
    "**结果（Result）**：峰值延迟降至 180ms，超时率从 3.2% 降到 0.1%，"
    "支撑了当年双十一 12 万笔/分钟的订单量，方案沉淀为团队通用组件。"
)


def test_empty_is_truncated():
    assert _looks_truncated("")
    assert _looks_truncated("   ")


def test_stub_answer_is_truncated():
    """实测出现过的 25 字残答"""
    assert _looks_truncated("我参与过订单中台的建设工作，主要负责后端开发。")


def test_long_text_without_structure_is_truncated():
    """长度够但没有 STAR 结构，同样视为不合格"""
    text = "我在项目中承担后端开发工作，参与了需求评审、接口设计与联调测试。" * 6
    assert len(text) >= MIN_ANSWER_CHARS
    assert _looks_truncated(text)


def test_complete_star_answer_passes():
    assert len(STAR_OK) >= MIN_ANSWER_CHARS
    assert not _looks_truncated(STAR_OK)


def test_english_star_labels_pass():
    text = (
        "Situation: backend owner of an order platform. "
        "Task: cut p99 latency below 200ms. "
        "Action: introduced async queuing and idempotent design. "
        "Result: latency dropped to 180ms with 0.1% timeout rate on peak traffic. "
    ) * 3
    assert not _looks_truncated(text)
