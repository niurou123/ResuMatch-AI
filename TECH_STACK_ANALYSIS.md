# ResuMatch AI — 技术选型全景分析

> 生成日期：2026-08-03（重建版）
> 基于项目实际代码库，覆盖 LLM、嵌入模型、向量数据库、后端框架、前端技术栈、RAG 增强技术等所有关键选型决策。
> 本文件纳入版本管理（git），如有重大技术变更请同步更新。

---

## 一、LLM 层

### 1.1 当前选型：DeepSeek v4-pro

| 维度 | 当前值 |
|------|--------|
| 模型 | `deepseek-v4-pro` |
| API 地址 | `https://api.deepseek.com/v1` |
| 协议 | OpenAI 兼容（`/v1/chat/completions`） |
| 超时 | 60s（可在 `DeepSeekClient` 构造时覆盖） |
| 客户端 | 自研 `DeepSeekClient`（httpx 异步 + 流式支持） |
| 代码位置 | [src/core/llm_client.py](src/core/llm_client.py) |

### 1.2 LLM 使用边界（关键约束）

- **简历解析层零 LLM 介入**：纯规则+正则提取，不概括/改写
- **LLM 仅允许**：字段标准化映射、智能位置匹配、分类判断、技术栈归类、面试回答生成、针对性简历润色
- **禁止**：编造简历中不存在的量化数据/时间线/项目
- 回答必须标注来源，缺失信息如实说明（"根据我的简历，这部分没有详细记录"）

### 1.3 横向对比：为什么选 DeepSeek v4-pro

| 维度 | **DeepSeek v4-pro（选用）** | GPT-4o | Claude Sonnet | Gemini 2.0 Flash | Qwen2.5-72B |
|------|---------------------------|--------|---------------|------------------|-------------|
| **中文理解** | 极佳（中文原生优化） | 优秀 | 优秀 | 优秀 | 极佳 |
| **推理成本** | 低（约 $0.28/M in，$0.42/M out） | 高（约 $2.50/M in） | 中高 | 低（但受配额） | 中 |
| **API 稳定性** | OpenAI 兼容，稳定 | 稳定 | 稳定 | 稳定 | 需自部署 |
| **长上下文** | 64K-128K | 128K | 200K | 1M | 32K-128K |
| **代码/逻辑** | 强 | 强 | 强 | 强 | 强 |
| **国内可直连** | ✅（无需代理） | ❌ 需代理 | ❌ 需代理 | ❌ 需代理 | 视部署 |
| **调用成本（本项目面试对练高频）** | ⭐ 最低 | 高 | 中高 | 低 | 中 |

**选择理由**：
1. **成本敏感**：面试对练/简历增强是高频 LLM 调用（一次回答 5-8 次调用），DeepSeek 成本最低，可无压力高频使用
2. **中文简历/面试场景**：DeepSeek 中文原生优化，理解中文简历、生成自然中文面试回答更佳
3. **国内网络直连**：无需代理/翻墙，部署简单稳定
4. **OpenAI 兼容协议**：`DeepSeekClient` 自研封装，未来可平滑切换其他 OpenAI 兼容模型

### 1.4 备用方案（可切换）

若 DeepSeek 不可用，`DeepSeekClient` 仅需改 `base_url`+`model` 即可切换：
- **Qwen 通义千问**（阿里，OpenAI 兼容，中文好）
- **GLM-4**（智谱，OpenAI 兼容，中文好）
- 兼容 OpenAI 协议的任何模型（GPT/Claude 需配代理）

---

## 二、嵌入模型

### 2.1 当前选型：BAAI/bge-small-zh

| 维度 | 当前值 |
|------|--------|
| 模型 | `BAAI/bge-small-zh` |
| 向量维度 | 512 维 |
| 加载方式 | 本地缓存优先（`HF_HUB_OFFLINE=1`），冷启动 10-20s |
| 缓存修复 | 曾因缓存缺 `1_Pooling`/tokenizer 导致上传 500，已补全 + 换 safetensors |
| 代码位置 | [src/rag/embedder.py](src/rag/embedder.py) |

### 2.2 性能优化

- **线程锁**：`threading.Lock` 防止多线程并发重复加载（冷启动 10-20s）
- **启动预热**：`main.py` lifespan 启动时预热嵌入+精排模型，首请求秒回

### 2.2 横向对比：为什么选 bge-small-zh

| 维度 | **bge-small-zh（选用）** | bge-large-zh | text2vec-large-chinese | m3e-base | OpenAI text-embedding-3 |
|------|------------------------|--------------|------------------------|----------|------------------------|
| **维度** | 512 | 1024 | 1024 | 768 | 1536 |
| **中文效果** | 强（中文特化） | 极强 | 强 | 中上 | 好 |
| **推理速度** | ⭐ 快（小模型） | 慢 | 慢 | 中 | 外部 API |
| **本地离线** | ✅ 可离线 | ✅ | ✅ | ✅ | ❌ 需 API |
| **存储开销** | ⭐ 低 | 高 | 高 | 中 | 高 |
| **中文命名实体/简历术语** | ⭐ 好 | 好 | 好 | 中 | 中 |

**选择理由**：bge-small-zh 在**中文简历检索场景**（技能名/项目名/成果描述）效果好，512 维平衡精度与速度/存储，且可完全本地离线运行（隐私友好，不依赖外部 API）。

---

## 三、Cross-Encoder 精排

| 维度 | 当前值 |
|------|--------|
| 模型 | `BAAI/bge-reranker-base` |
| 用途 | Bi-Encoder 初检 Top-K → Cross-Encoder 逐对打分精排 |
| 精度提升 | ↑10-20% |
| 代码位置 | [src/rag/reranker.py](src/rag/reranker.py) |

---

## 四、向量数据库

| 维度 | 当前值 |
|------|--------|
| 方案 | ChromaDB（`chromadb>=0.5.0`） |
| 持久化 | `data/chroma_db` |
| 集合 | skills / projects / achievements / education（四集合） |
| 度量 | 余弦相似度（`hnsw:space=cosine`） |
| 代码位置 | [src/rag/vector_store.py](src/rag/vector_store.py) |

**注意**：ChromaDB 存储的是被父子分块切碎的 child chunk，**项目-JD 匹配读取结构化档案（data/profile.json）而非 ChromaDB**（更可靠）。

---

## 五、后端框架

| 维度 | 当前值 |
|------|--------|
| 框架 | FastAPI `0.104.1` |
| 端口 | 8000（前端连 8004） |
| 工作流 | LangGraph（`langgraph>=0.2.0`）多 Agent 协作 |
| 状态管理 | `AgentState`（Pydantic）+ `MemorySaver` 检查点 |
| 并发 | asyncio.gather 并行检索 + 并行评审 |
| API 端点 | 14+ 个（简历/面试/模拟面试/档案/JD匹配/系统） |
| 代码位置 | [src/api/routes.py](src/api/routes.py) |

---

## 六、前端技术栈

| 维度 | 当前值 |
|------|--------|
| 主框架 | React 19 + TypeScript + Vite 8 |
| UI | Tailwind CSS 3 + lucide-react 图标 |
| 路由 | react-router-dom 7 |
| 数据请求 | @tanstack/react-query + fetch（SSE 流式自研） |
| 页面 | 简历上传 / 档案 / 面试模拟 / 自我介绍 / JD 匹配 |
| 代码位置 | [frontend/src/](frontend/src/) |
| 状态 | Streamlit 已弃用（app.py 仅历史保留） |

### 前端特性

- 深色渐变主题（#0a0a1a + 蓝紫渐变 #6366f1→#8b5cf6）
- 多 Agent 工作流 DAG 可视化（Planner→Router→检索→Writer→评审→完成）
- 面试对练：AI 候选人模式 + AI 生成问题（项目选择/追问·新问题）
- 语音输入提问（Web Speech API，中文识别，零依赖）
- 档案管理：简历自动解析 + 手动完善项目细节（动态分点列表）

---

## 七、RAG 增强技术（6 项）

| 技术 | 说明 | 代码位置 |
|------|------|----------|
| **HyDE 假设文档嵌入** | LLM 生成假设回答 → 用其向量检索（Recall@5 ↑15-25%） | [src/rag/hyde.py](src/rag/hyde.py) |
| **Self-Query 结构化检索** | LLM 将自然语言翻译为 ChromaDB metadata 过滤条件 | [src/rag/self_query.py](src/rag/self_query.py) |
| **Cross-Encoder 精排** | Bi-Encoder 初检 → Cross-Encoder 逐对打分 | [src/rag/reranker.py](src/rag/reranker.py) |
| **Parent-Child 父子分块** | 子块检索 → 父块完整段落入 LLM | [src/rag/chunker.py](src/rag/chunker.py) |
| **Skill Graph 知识图谱** | 16 技术类别 × 80+ 节点，归类词→技能展开 | [src/rag/knowledge_graph.py](src/rag/knowledge_graph.py) |
| **LLM-as-Judge 评测** | 5 维自动评分（相关性/STAR完整性/优势/量化密度/真实性） | [src/agents/reviewer.py](src/agents/reviewer.py) |

---

## 八、多 Agent 工作流架构

```
Planner（动态调度）
  → Router（规则化分类，0s）
  → 3 路并行检索（keyword/semantic/graph，asyncio.gather）
  → Fusion 投票融合
  → STAR Writer（引用约束 + Agent 通信）
  → 3 路并行评审（正确性/完整性/优势，多数表决）
  → 修订回环（最多 3 轮）
```

**快速模式**：面试对练跳过评审/修订 + HyDE，回答提速 3-4 倍。

**项目归属约束**：检索素材标注 `[项目: xxx]`，问题提到某项目时定向召回/剔除跨项目素材，防张冠李戴。

---

## 九、简历解析（数据质量根基）

| 维度 | 当前值 |
|------|--------|
| 库 | PyMuPDF / python-docx / mammoth（XML 回退） |
| 提取 | 纯规则 + 正则，零 LLM 介入 |
| 来源追踪 | 每字段标注行号 + 原始文本 + 方法 + 置信度 |
| 结构化 | 14 分区 / 200+ 字段（resume-schema v3） |
| 项目字段 | name/role/tech_stack/time_period/key_result/description/details/difficulties/challenges/responsibilities |
| 代码位置 | [src/rag/parser.py](src/rag/parser.py) |

---

## 十、数据存储与档案

| 维度 | 当前值 |
|------|--------|
| 结构化档案 | `data/profile.json`（ProfileStore 原子读写） |
| 向量库 | ChromaDB `data/chroma_db` |
| 原始简历 | `data/resumes/`（隐私，git 忽略） |
| 代码位置 | [src/features/profile_store.py](src/features/profile_store.py) |

---

## 十一、性能与可靠性

- 嵌入模型预热 + 线程锁（首请求 10-20s → 秒回）
- 快速模式跳过评审/修订/HyDE（面试对练提速 3-4 倍）
- 错误隔离（单 Agent 失败不影响整体）
- 退路机制（LLM 不可用 → 规则化降级；简历未覆盖 → 技术推理回答）
- Bug 案例记录于 [BUG_LOG.md](BUG_LOG.md)

---

## 十二、测试

| 维度 | 当前值 |
|------|--------|
| 框架 | pytest |
| 覆盖 | 简历解析 → 向量检索 → Agent 工作流全链路 |
| 面试类型 | 技术深度/项目追问/行为面试/通用问题 |

---

## 十三、Python 开发能力与技术栈

### 13.1 语言与运行环境

| 维度 | 当前值 |
|------|--------|
| 语言 | Python 3.10+ |
| 包管理 | pip + requirements.txt（纯 ASCII） |
| 类型标注 | TypedDict / Pydantic（`AgentState`、API schemas） |
| 异步 | async/await（FastAPI、LLM 客户端、asyncio.gather 并行） |
| 代码位置 | [src/](src/) 全部后端 |

### 13.2 核心 Python 技术栈

| 库/框架 | 版本 | 用途 |
|---------|------|------|
| **FastAPI** | 0.104.1 | Web 框架，14+ RESTful 端点 + SSE 流式 |
| **LangGraph** | ≥0.2.0 | 多 Agent 有状态工作流（MemorySaver 检查点） |
| **ChromaDB** | ≥0.5.0 | 向量数据库（5 集合，含 project_docs） |
| **sentence-transformers** | ≥3.0.0 | 嵌入模型加载（bge-small-zh + reranker） |
| **PyMuPDF / python-docx / mammoth** | — | 简历 PDF/DOCX 解析（含 XML 回退） |
| **httpx** | — | 异步 LLM API 客户端（流式 + 超时控制） |
| **pydantic** | — | 数据模型 + 校验（AgentState / schemas） |
| **python-dotenv** | — | 环境变量加载（.env） |
| **pytest** | — | 端到端测试 |

### 13.3 项目用到的 Python 高级能力

1. **异步并发**：`asyncio.gather` 真正并行 3 路检索 + 3 路评审，总耗时 = max(单路) 而非 sum
2. **线程安全模型加载**：`threading.Lock` + 双重检查，防多线程并发重复加载嵌入模型
3. **事件循环隔离**：`run_in_executor` 线程池跑简历解析，规避 ChromaDB 与 asyncio 递归冲突（`sys.setrecursionlimit`）
4. **原子文件写入**：`tempfile.mkstemp` + `os.replace` 原子写 `profile.json`，防写坏
5. **流式 SSE**：`StreamingResponse` + `async for` 实现问答流式输出
6. **Pydantic 校验**：`AgentState` 状态机 + API 请求/响应模型 + LLM 结构化输出
7. **错误隔离与退路**：每 Agent 独立 try/except，单 Agent 失败不影响整体；LLM 不可用时规则化降级

### 13.4 为什么 Python 适合本项目

- **AI 生态最成熟**：LangGraph / sentence-transformers / ChromaDB 等 Agent 与 RAG 生态一应俱全
- **快速迭代**：动态类型 + 丰富库，适合功能快速演进
- **异步 + 科学计算**：asyncio 处理高并发 LLM 调用，配合 numpy 向量运算
- **生态兼容**：DeepSeek / OpenAI / 各家 LLM 均有 Python SDK，切换模型成本低

---
