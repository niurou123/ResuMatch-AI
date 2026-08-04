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
| 集合 | skills / projects / achievements / education / project_docs（五集合） |
| 度量 | 余弦相似度（`hnsw:space=cosine`） |
| 代码位置 | [src/rag/vector_store.py](src/rag/vector_store.py) |

**注意**：ChromaDB 存储的是被父子分块切碎的 child chunk，**项目-JD 匹配读取结构化档案（data/profile.json）而非 ChromaDB**（更可靠）。

### 4.1 横向对比：为什么选 ChromaDB

| 维度 | **ChromaDB（选用）** | FAISS | Milvus | Qdrant | Weaviate | Elasticsearch |
|------|---------------------|-------|--------|--------|----------|---------------|
| **部署** | 轻量嵌入式 | 库 | 服务 | 服务 | 服务 | 服务 |
| **本地单机** | ✅ 零运维 | ✅ | 较重 | 可 | 可 | 较重 |
| **持久化** | 内置 | 需自管 | 内置 | 内置 | 内置 | 内置 |
| **metadata 过滤** | ✅ 原生 | 弱 | ✅ | ✅ | ✅ | ✅ |
| **异步/同步** | 同步 | 同步 | 客户端 | 客户端 | 客户端 | 客户端 |
| **学习成本** | ⭐ 低 | 中 | 高 | 中 | 高 | 高 |
| **本项目简历小规模数据** | ⭐ 最合适 | 过重 | 过重 | 过重 | 过重 | 过重 |

**选择理由**：本项目简历数据量小（几十到几百条向量），ChromaDB **嵌入式零部署、原生 metadata 过滤、API 简单**，完全够用且易维护。FAISS 需自管持久化和过滤；Milvus/Qdrant 等服务型方案对本项目属于过度设计。

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

### 5.1 横向对比：为什么选 FastAPI

| 维度 | **FastAPI（选用）** | Flask | Django REST | Spring Boot (Java) | Express (Node) |
|------|--------------------|-------|-------------|-------------------|----------------|
| **异步原生** | ✅ 原生 async | 弱 | 弱 | 可 | ✅ |
| **性能** | ⭐ 高 | 中 | 中 | 高 | 高 |
| **类型校验** | ✅ Pydantic 自动 | ❌ | 有 | 有 | 弱 |
| **OpenAPI 文档** | ✅ 自动生成 | ❌ | 部分 | 部分 | 部分 |
| **SSE 流式** | ✅ 原生 | 需插件 | 复杂 | 复杂 | 可 |
| **AI/异步生态契合** | ⭐ 最佳 | 一般 | 一般 | 一般 | 可 |
| **与 Python AI 库协同** | ⭐ 无缝 | 一般 | 一般 | ✗ 跨语言 | ✗ |

**选择理由**：FastAPI **原生 async** 完美契合 asyncio 多 Agent 并行；**Pydantic 自动校验**（AgentState + API schema 同构）；**自动 OpenAPI 文档**；**SSE 流式**原生支持面试问答流式输出。相比 Flask 更强性能与类型安全，相比 Django 更轻量异步友好，相比 Java/Node 能与 Python AI 生态（LangGraph/ChromaDB/sentence-transformers）无缝协同。

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

### 6.1 横向对比：为什么选 React + Vite + TypeScript

| 维度 | **React+Vite+TS（选用）** | Vue3+Vite | Next.js | Streamlit (旧) | Chrome 插件 vanilla JS |
|------|--------------------------|-----------|---------|----------------|------------------------|
| **类型安全** | ✅ TS 强类型 | 可选 | ✅ | ❌ | ❌ |
| **组件生态** | ⭐ 最丰富 | 丰富 | 丰富 | 弱 | 弱 |
| **构建速度（HMR）** | ✅ Vite 极快 | ✅ | 中 | 重 | — |
| **SSE/实时交互** | ✅ 灵活 | ✅ | ✅ | 受限 | 受限 |
| **复杂前端能力**（DAG可视化/动态表单/语音） | ⭐ 强 | 强 | 强 | 弱 | 弱 |
| **后端解耦** | ✅ 纯前后端分离 | ✅ | 全栈耦合 | 强耦合 | 弱 |

**选择理由**：
1. **Streamlit 弃用的原因**：Streamlit 擅长快速原型，但**难以承载复杂交互**（DAG 可视化、动态分点表单、语音识别），且与后端强耦合，不适合做专业工具型产品——这也是本项目从 Streamlit 迁移到 React 的动因
2. **React + TS**：强类型保障前端稳定性，组件生态最全，适合多 Agent 可视化等复杂 UI
3. **Vite**：HMR 极快，开发体验好
4. **前后端分离**：React 只通过 REST/SSE 调 FastAPI，清晰解耦
5. **Chrome 扩展单独用 vanilla JS**：扩展场景轻量，无需 React 打包

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

### 7.1 分块策略对比：为什么用 Parent-Child

| 维度 | **Parent-Child 父子分块（选用）** | 固定长度分块 | 语义分块（textsplitter） | 整文档入上下文 |
|------|--------------------------------|--------------|--------------------------|----------------|
| **检索精度** | ✅ 高（小粒度召回） | 中 | 高 | 低（噪声多） |
| **上下文完整性** | ✅ 父块全段落 | 中 | 高 | 高 |
| **实现复杂度** | 中 | 低 | 中 | 最低 |
| **token 效率** | ⭐ 最优 | 中 | 高 | 差 |
| **简历/项目文档适配** | ⭐ 最合适（句子切分 + 完整段落） | 一般 | 一般 | 不适合长文档 |

**选择理由**：简历和项目文档既需要**小粒度精确召回**（技能名/项目名），又需要**完整段落上下文**（STAR 回答引用），Parent-Child 恰好兼顾两者，且比整文档入上下文 token 高效。

### 7.2 检索策略对比：为什么 3 路并行 + Fusion

| 维度 | **3路并行检索（选用）** | 单一向量检索 | 仅关键词 | 单路混合检索 |
|------|------------------------|--------------|----------|--------------|
| **召回全面性** | ⭐ 高（关键词+语义+图谱互补） | 中 | 低 | 中 |
| **精确匹配**（技能/项目名） | ✅ keyword 路 | 弱 | ✅ | 中 |
| **语义理解**（"最大挑战"→优化） | ✅ semantic 路（HyDE） | ✅ | 弱 | 中 |
| **知识推理**（"向量数据库"→FAISS/ChromaDB） | ✅ graph 路 | 弱 | 弱 | 弱 |
| **耗时** | 高（并行后=max 单路） | 低 | 低 | 中 |

**选择理由**：面试问题类型多样（技术/项目/行为/通用），单一检索策略覆盖不全。3 路并行互补召回 + Fusion 投票加权，兼顾精确匹配、语义理解和知识推理；`asyncio.gather` 并行使总耗时 = 最慢单路，而非累加。

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

## 十二、Redis（会话持久化 + LLM 语义缓存）

### 12.1 当前选型

| 维度 | 当前值 |
|------|--------|
| 服务 | Redis 5.0.14（Windows 便携版，tporadowski 移植）|
| 客户端 | redis-py ≥5.0（`protocol=2` 兼容 Redis 5.x）|
| 地址 | `localhost:6379`（config：REDIS_HOST/PORT/DB）|
| 代码位置 | [src/core/redis_store.py](src/core/redis_store.py) |

### 12.2 应用场景（已落地）

1. **会话状态持久化**：mock 面试会话存 Redis（`session:{id}`，JSON + TTL 过期），替代内存 dict `_sessions`
   - 服务重启不丢会话（实测：跨重启 round 1→2）
   - 多实例部署可共享会话
2. **LLM 语义缓存**：面试对练回答缓存（相同问题+项目命中秒回），key 含 model + question + 简历上下文哈希
   - 省 LLM 调用成本/延迟（一次回答 5-8 次调用）
   - 上传新项目文档时自动失效缓存（`flush_prefix`）
3. **降级退路**：Redis 不可用（未装/未启动/连接失败）→ 自动回退内存 dict，功能不受影响

### 12.3 缓存策略设计

| 项 | 设计 |
|----|------|
| Key 设计 | `cache:{prefix}:{sha256(model+prompt+参数)}` 分层语义化 |
| TTL | 会话 1h、LLM 缓存 1天（config 可调）|
| 失效 | 上传项目文档 → `flush_prefix("mock_answer")` 清缓存 |
| 兼容 | `protocol=2` 兼容 Redis 5.x（新 redis-py 默认 HELLO 3 会报错）|
| 穿透防护 | 缓存空值/短 TTL，避免反复打 LLM |

### 12.4 为什么 Redis 适合本项目

- 面试对练高频 LLM 调用 → 语义缓存收益大（省成本/延迟）
- 会话需跨重启/多实例 → Redis 集中存储
- 轻量嵌入式启动（Windows 便携版免安装）→ 开发环境易用

---

## 十三、测试

| 维度 | 当前值 |
|------|--------|
| 框架 | pytest |
| 覆盖 | 简历解析 → 向量检索 → Agent 工作流全链路 |
| 面试类型 | 技术深度/项目追问/行为面试/通用问题 |

---

## 十四、Python 开发能力与技术栈

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
