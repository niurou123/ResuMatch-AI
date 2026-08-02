# ResuMatch AI — 多Agent面试 + 网申助手

基于多Agent协作的AI校招助手。简历智能解析、网申一键填充、面试问答生成。

## 核心场景

1. **上传简历** → AI 纯规则提取结构化数据 → 本地档案存储
2. **打开网申页面** → 扫描表单 → 一键智能填充
3. **输入面试问题** → 多Agent并行检索 + 评审 → STAR 格式回答

---

## 技术架构 (v3.0)

```
Chrome Extension (Manifest V3)     │  Python Backend (FastAPI) — 多Agent并行架构
───────────────────────────────────┼──────────────────────────────────────────
popup.js: 扫描+本地匹配+填充        │  Planner → Router → 3路并行检索Agent
  - 120+规则本地毫秒匹配             │    (keyword/semantic/graph, asyncio.gather)
  - LLM兜底(仅未匹配字段)            │  → Fusion投票 → Writer(Agent通信)
                                    │  → 3路并行Reviewer(正确性/完整性/优势)
sidebar.js: 简历上传+档案编辑       │  → 多数表决 → END/Revise回环
content.js: 表单扫描+填充执行        │
background.js: 消息路由              │  RAG管道: 解析器v2.0 + 标准化映射层
resume-editor: 14分区完整编辑器      │  10个API端点 + 来源追踪 + 验证报告
```

### 6 节点 LangGraph 工作流

| 节点 | 职责 |
|------|------|
| **DynamicPlanner** | 按问题类型动态调度Agent（5种策略） |
| **QuestionRouter** | 规则化问题分类 + 难度评估（0s延迟） |
| **ParallelRetrieval** | 3路并行检索 (关键词/语义/知识图谱) → Fusion |
| **STARWriter** | 流式生成 + Agent通信自我修正 |
| **ParallelReview** | 3路并行评审 (正确性/完整性/优势) → 多数表决 |

---

## 快速开始

### 前置要求

- Python 3.10+
- DeepSeek API Key
- Chrome 114+（使用扩展功能）

### 安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境
cp .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY

# 3. 启动后端
python -m src.api.main

# 4. 启动前端（React，新终端）
cd frontend
npm install
npm run dev
# 默认 http://localhost:5173
```

### 加载 Chrome 扩展

1. 打开 `chrome://extensions/`
2. 开启「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `extension/` 目录

### 使用流程

1. 打开 http://localhost:5173 或点击扩展图标
2. 上传简历（PDF/Word/Markdown/TXT）
3. 在「面试模拟」输入问题，获取 STAR 格式回答
4. 打开网申页面，点击「扫描页面」→「一键填充」
5. 使用「JD 匹配」分析职位匹配度

---

## 项目结构

```
interview-rag-system/
├── CLAUDE.md                   # AI 开发指南（最高优先级）
├── SPEC.md                     # 功能规格文档（项目大脑）
├── app.py                      # ⚠️ DEPRECATED — Streamlit 前端（已迁移至 frontend/ React）
│
├── src/
│   ├── agents/                 # LangGraph 多Agent工作流 (v3.0)
│   │   ├── graph.py             # 工作流组装 + 条件边
│   │   ├── state.py             # AgentState 全局状态
│   │   ├── planner.py           # DynamicPlanner (5种调度策略)
│   │   ├── router.py            # QuestionRouter (规则化,0s延迟)
│   │   ├── retriever_node.py    # 3路并行检索 + Fusion
│   │   ├── writer.py            # STARWriter + Agent通信
│   │   ├── reviewer.py          # 3路并行评审 + 多数表决
│   │   └── communication.py     # Agent间双向通信协议
│   │
│   ├── rag/                    # RAG 管道层
│   │   ├── parser.py            # 简历解析器 v2.0 (来源追踪+置信度)
│   │   ├── normalizer.py        # LLM字段标准化映射 (不概括)
│   │   ├── chunker.py           # Parent-Child 父子分块
│   │   ├── embedder.py          # bge-small-zh 嵌入 (512维)
│   │   ├── vector_store.py      # ChromaDB 4集合管理
│   │   ├── self_query.py        # Self-Query 结构化查询
│   │   ├── hyde.py              # HyDE 假设文档检索
│   │   ├── reranker.py          # Cross-Encoder 精排
│   │   └── knowledge_graph.py   # 技能知识图谱
│   │
│   ├── core/                   # 核心服务层
│   │   ├── llm_client.py        # DeepSeek API 客户端
│   │   ├── prompts.py           # Jinja2 动态模板
│   │   ├── memory.py            # 三层会话记忆
│   │   └── judge.py             # LLM-as-Judge 评测
│   │
│   ├── features/               # 业务功能层
│   │   ├── self_intro.py        # 自我介绍生成器
│   │   ├── mock_interview.py    # 模拟面试引擎
│   │   ├── jd_matcher.py        # JD匹配度分析 (技能级)
│   │   ├── project_matcher.py   # 项目-JD匹配引擎 (三维度)
│   │   └── profile_store.py     # 结构化档案/项目库持久化 (JSON)
│   │
│   └── api/                    # FastAPI 层
│       ├── main.py              # 应用入口 + CORS
│       ├── routes.py            # 10+ API端点
│       └── schemas.py           # Pydantic 请求/响应模型
│
├── frontend/                   # React 前端 (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── pages/               # 简历上传/面试/自我介绍/JD匹配
│   │   ├── lib/                 # api.ts / types.ts / constants.ts
│   │   └── components/          # 布局与共享组件
│   └── package.json
│
├── extension/                  # Chrome 扩展 (Manifest V3)
│   ├── manifest.json
│   ├── background.js            # Service Worker + 消息路由
│   ├── content.js               # 页面注入 + 表单扫描填充
│   ├── popup/                   # 弹出窗口 (扫描+填充)
│   ├── sidebar/                 # 侧边栏 (简历上传+档案编辑)
│   ├── lib/                     # 共享库
│   │   ├── resume-schema.js     # 14分区/200+字段 Schema
│   │   ├── template.js          # 字段映射引擎 (50+规则)
│   │   └── api.js               # API 桥接层
│   ├── resume-editor.html       # 独立简历编辑器 (14分区)
│   └── resume-editor.js
│
├── tests/                      # 测试套件
│   ├── conftest.py
│   ├── test_parser.py           # 10项解析器测试
│   └── test_vector_store.py     # 8项向量存储测试
│
├── data/
│   ├── resumes/                 # 简历文件
│   └── chroma_db/               # ChromaDB 持久化
│
├── requirements.txt
└── .env
```

---

## API 端点

```yaml
POST /api/v1/resume/upload        # 上传简历 (返回验证报告+来源追踪)
GET  /api/v1/resume/profile       # 获取简历画像

POST /api/v1/interview/answer     # 单次面试问答
POST /api/v1/interview/stream     # 流式问答 (SSE)

POST /api/v1/mock/start           # 开始模拟面试
POST /api/v1/mock/next            # 下一轮追问

POST /api/v1/form/fill            # 智能表单填充 (LLM驱动)
POST /api/v1/intro/generate       # 生成自我介绍
POST /api/v1/match/analyze        # JD匹配度分析

GET  /api/v1/health               # 健康检查
GET  /api/v1/system/info          # 系统信息
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React (Vite + TypeScript + Tailwind) — frontend/, Chrome Extension MV3 |
| 后端 | Python, FastAPI, LangGraph |
| LLM | DeepSeek v4-pro |
| 向量库 | ChromaDB, bge-small-zh (512维) |
| 解析 | PyMuPDF, python-docx, mammoth |
| 精排 | bge-reranker-base (Cross-Encoder) |
| 测试 | pytest |

---

## 运行测试

```bash
pytest tests/ -v
pytest tests/test_parser.py -v
```

---

## 路线图

| 优先级 | 模块 | 状态 |
|--------|------|------|
| P0 | 简历如实提取 (来源追踪+置信度) | ✅ |
| P1 | 多Agent并行架构 | ✅ |
| P1 | 项目经验库 + JD智能匹配 | ⏳ |
| P2 | UI品质升级 (深色渐变主题) | ✅ |
| P2 | 网申填充增强 | ⏳ |
| P3 | OCR / 简历编辑器 / 进度追踪 | ⏳ |

详见 [SPEC.md](SPEC.md)
