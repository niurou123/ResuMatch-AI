# 设计方案：Bug 修复 + 补测试

**日期**: 2026-06-07
**状态**: 待审查

---

## 目标

修复阻断性 bug，补齐测试，让项目可运行、可展示。

## 约束

- 技术栈不变
- 目录结构不变（平铺 + 新增 `tests/`）
- 不新增功能

---

## 第一部分：Bug 修复

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| 1 | retrieval.py:40 | `settings.ensure_directories()` 方法不存在 | 改为 `ensure_directories()` |
| 2 | init_project.py:9 | 硬编码绝对路径 | 改为 `Path(__file__).parent.resolve()` |
| 3 | config.py:21 | `DEEPSEEK_API_KEY` 必填，缺 `.env` 直接崩溃 | 加 `default=""`，启动时友好提示 |
| 4 | evaluator.py:167 | `compute_rouge_n` 只算了 Recall | 补全 Precision + Recall + F1 |
| 5 | app.py:10 | API URL 硬编码 | 从环境变量 `API_URL` 读取，默认 `localhost:8000` |

---

## 第二部分：测试

### 目录

```
tests/
├── conftest.py              # 共享 fixtures
├── test_retrieval.py        # FAISS/BM25/RRF 检索
├── test_evaluator.py        # EM/BLEU/ROUGE 计算
├── test_inference.py        # Prompt 模板 + 推理调用
└── test_api.py              # FastAPI 端点
```

### 覆盖范围

| 测试文件 | 用例数（估） | 验证点 |
|----------|------------|--------|
| test_retrieval.py | 8-10 | FAISS 检索、BM25 分词、RRF 融合排序、方法路由 |
| test_evaluator.py | 8-10 | EM 规范化、BLEU n-gram、ROUGE-L LCS、代码提取 |
| test_inference.py | 6-8 | 三种 prompt 格式、API 调用参数、流式/非流式 |
| test_api.py | 6-8 | /health、推理三种模式、检索三种方法、评测端点 |
| **总计** | **~32** | |

### 策略

- 检索/评测用真实数据测试（小样本），不 mock SentenceTransformer
- DeepSeek API 全部 mock
- API 测试用 FastAPI TestClient

---

## 执行顺序

1. Bug 修复（5 项）
2. 测试编写（conftest → retrieval → evaluator → inference → api）
3. 全量测试运行验证
