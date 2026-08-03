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
