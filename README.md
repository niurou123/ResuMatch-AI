# 🤖 ResuMatch AI - Agent 面试助手

基于多 Agent 协作的 AI 面试助手。蒸馏个人简历，向量化优势，智能生成个性化面试回答。

## 🎯 核心理念

**你提问，AI 回答 —— 基于你的真实经历。**

上传简历（PDF/Word），系统自动解析并向量化。任何面试问题都能得到基于你真实项目经验的 STAR 格式回答，引用具体数据和成果。

---

## 🏗️ 技术架构

```
用户提问 → QuestionRouter(0s) → HyDE + Self-Query → 并行检索4源
                                        ↓
            ChromaDB (skills/projects/achievements/education)
                                        ↓
            Cross-Encoder 精排 → STARWriter(流式) → QualityReviewer(5维评分)
                                        ↑                    │
                                        └── N轮修订 ──────────┘
```

### 5 节点 LangGraph 工作流

| 节点 | 职责 | 延迟 |
|------|------|------|
| **ProfileAnalyzer** | 简历解析 + 向量化 | 初始化一次性 |
| **QuestionRouter** | 规则化问题分类 | **0s**（无 LLM） |
| **ExperienceRetriever** | HyDE + Self-Query + 并行检索 + Cross-Encoder 精排 | 3-10s |
| **STARWriter** | 流式生成 + 强制引用约束 | 首字 < 2s |
| **QualityReviewer** | LLM-as-Judge 5维评分 + 条件修订 | 1-3s |

### 6 项核心技术突破

| 技术 | 解决什么问题 |
|------|------------|
| **Self-Query** | 向量搜索无法利用结构化字段 → LLM生成带metadata过滤的查询 |
| **HyDE** | 问题与简历语义不匹配 → 先生成假设回答再检索 |
| **Cross-Encoder** | Bi-Encoder精度不足 → top-20重排至top-5 |
| **Parent-Child Chunking** | 项目描述被切断 → 子块检索+父块送LLM |
| **LLM-as-Judge** | 无客观质量指标 → 5维结构化评分建立基线 |
| **Skill Graph** | "向量数据库"找不到"FAISS" → 知识图谱查询扩展 |

---

## 🚀 快速开始

### 前置要求

- Python 3.10+
- DeepSeek API Key

### 安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境
cp .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY

# 3. 启动 API
python -m src.api.main

# 4. 启动前端（新终端）
streamlit run app.py
```

### 使用流程

1. 打开 http://localhost:8501
2. 在「简历上传」页面上传你的简历（PDF/Word）
3. 进入「面试模拟」页面，输入面试问题
4. 获取基于你真实经历的 STAR 格式回答
5. 使用「自我介绍」生成器制作定制化自我介绍
6. 使用「JD 匹配」分析职位匹配度

---

## 📁 项目结构

```
interview-rag-system/
├── src/
│   ├── agents/              # LangGraph 5节点工作流
│   │   ├── graph.py          # 工作流组装 + 条件边
│   │   ├── state.py          # AgentState 状态定义
│   │   ├── planner.py        # Node 1: ProfileAnalyzer
│   │   ├── router.py         # Node 2: QuestionRouter(0s)
│   │   ├── retriever_node.py # Node 3: ExperienceRetriever
│   │   ├── writer.py         # Node 4: STARWriter(流式)
│   │   └── reviewer.py       # Node 5: QualityReviewer
│   │
│   ├── rag/                 # RAG 管道层
│   │   ├── parser.py         # PDF/DOCX 简历解析器
│   │   ├── chunker.py        # Parent-Child 父子分块
│   │   ├── embedder.py       # bge-small-zh 嵌入(512维)
│   │   ├── vector_store.py   # ChromaDB 4集合管理
│   │   ├── self_query.py     # Self-Query 结构化查询
│   │   ├── hyde.py           # HyDE 假设文档检索
│   │   ├── reranker.py       # Cross-Encoder 精排
│   │   └── knowledge_graph.py # 技能知识图谱
│   │
│   ├── core/                # 核心服务层
│   │   ├── llm_client.py     # DeepSeek API 客户端
│   │   ├── prompts.py        # Jinja2 动态模板
│   │   ├── memory.py         # 三层会话记忆
│   │   └── judge.py          # LLM-as-Judge 评测
│   │
│   ├── features/            # 业务功能层
│   │   ├── self_intro.py     # 自我介绍生成器
│   │   ├── mock_interview.py # 模拟面试引擎
│   │   └── jd_matcher.py     # JD匹配度分析
│   │
│   └── api/                 # FastAPI 层
│       ├── main.py           # 应用入口
│       ├── routes.py         # 10个API端点
│       └── schemas.py        # Pydantic模型
│
├── tests/                   # 测试套件
│   ├── conftest.py
│   ├── test_parser.py        # 简历解析器测试
│   └── test_vector_store.py  # 向量存储测试
│
├── data/
│   ├── resumes/              # 简历文件
│   └── chroma_db/            # ChromaDB 持久化
│
├── app.py                    # Streamlit 前端
├── requirements.txt
└── .env
```

---

## 🔌 API 端点

```yaml
POST /api/v1/resume/upload        # 上传简历
GET  /api/v1/resume/profile       # 获取简历画像

POST /api/v1/interview/answer     # 单次面试问答
POST /api/v1/interview/stream     # 流式问答(SSE)

POST /api/v1/mock/start           # 开始模拟面试
POST /api/v1/mock/next            # 下一轮追问

POST /api/v1/intro/generate       # 生成自我介绍
POST /api/v1/match/analyze        # JD匹配度分析

GET  /api/v1/health               # 健康检查
GET  /api/v1/system/info          # 系统信息
```

---

## 🧪 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行指定测试文件
pytest tests/test_parser.py -v
pytest tests/test_vector_store.py -v

# 带覆盖率报告
pytest tests/ --cov=src --cov-report=term
```

---

## ⚙️ 关键配置

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_MODEL=deepseek-chat

# 嵌入模型（中文优化）
EMBEDDING_MODEL=BAAI/bge-small-zh

# ChromaDB
CHROMA_DB_PATH=data/chroma_db

# 工作流参数
MAX_REVISION_ROUNDS=3
MIN_REVIEW_SCORE=20

# 会话记忆
SHORT_TERM_MAX_TURNS=10
MEMORY_MAX_TOKENS=4000
```

---
