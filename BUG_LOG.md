# 错误案例记录（Bug Log）

> 本会话中出现的错误/异常案例，逐一记录根因与解决方案。
> 格式：日期 | 现象 | 根因 | 解决方案 | 涉及文件

---

## 2026-08-02

### 案例 7：STAR 回答编造量化数据/时间线（幻觉）

**现象**：面试回答中出现简历素材中不存在的编造内容——"2024年初启动项目""计划2025年Q2上线""200份简历验证4.2/5""提高34%（2024年9月数据）"。虽然项目归属正确（ResuMatch），但时间线和量化成果全是虚构。

**根因**：`STAR_SYSTEM_PROMPT` 中"量化成果: 优先引用具体的数字和百分比"与"真实性第一"**自相矛盾**——prompt 鼓励引用数字，LLM 在素材没有量化数据时便自行编造。评审的 authenticity 维度虽能识别（评分仅 4.3-4.7/25），但 writer 侧缺少"禁止编造"的强约束。

**解决方案**（[src/core/prompts.py](src/core/prompts.py)）：重写 `STAR_SYSTEM_PROMPT`，新增「禁止编造」独立章节：
- 素材中没有的量化数据（百分比/倍率/指标/评分/人数）一律不得编造
- 禁止编造时间线（项目启动时间、上线计划）
- 缺失时明确说"根据我的简历，这部分信息暂时没有详细记录"

**验证**：重新生成回答——编造数字消失；writer 诚实标注"graph检索细节没有详细记录"、"没有记录具体量化指标"；真实素材的 Recall@5 15-25% 正确保留。

---

### 案例 8：多轮模拟角色颠倒 + 硬编码追问

**现象**：多轮模拟功能逻辑错误——AI 当面试官硬编码追问（不看回答内容），且用户实际需求是"用户当面试官提问，AI 基于简历回答"。

**根因**：后端 `/mock/next` 用硬编码问题（"请详细说说你在项目中遇到的最大技术挑战..."），完全忽略用户回答；`MockInterviewEngine` 存在但未被路由使用。

**解决方案**：
1. [routes.py](src/api/routes.py)：`/mock/next` 改为接受面试官 `question`，用 `run_interview_workflow`（多Agent工作流）基于简历生成 STAR 回答，返回 `ai_answer/question_type/review_total` 等
2. [schemas.py](src/api/schemas.py)：`MockInterviewNextRequest` 增加 `question` 字段，Response 增加 `ai_answer` 等
3. [Interview.tsx](frontend/src/pages/Interview.tsx)：MockInterview 组件反向改造——"面试对练设置"开始面板 → 面试官输入问题 → 展示 AI 候选人回答（含问题类型标签+评分）→ 可继续追问

**验证**：浏览器端到端——提问"视觉康复技术栈" → AI 回答聚焦视觉康复（Taro/uni-app/Vue3/RBAC，全真实），诚实说明无量化数据，第 2 轮追问正常切换。

---

## 2026-08-02

### 案例 6：面试回答空/截断 + 总分 6.5/25 + 修订 3 轮死循环

**现象**：React 面试页提问"介绍一下你的 AI Agent 项目"，回答截断在"1. 意图快速响应：用户提问"就断了，引用 0 条，总分 6.5/25，修订 3 轮后仍是残篇。多次运行表现不稳定（偶发空回答）。

**根因**（逐层定位）：
1. **`ParentChildChunker` 三目表达式优先级错误**（[chunker.py:91](src/rag/chunker.py#L91)）：
   ```python
   child_text = "。".join(group) + "。" if group[-1].endswith("。") else ""
   ```
   被解析为 `(A + B) if C else ""`——当分组句子末尾不是句号时，整个 chunk 被赋为**空串**。
   `_split_sentences` 按逗号切长句，导致很多句子末尾无句号 → **31/42 条 achievement chunk 是空字符串**（占 74%）。
2. **空 chunk 存入 ChromaDB**：`_index_batch` 对空 content 用 `"{collection} #{index}"` 占位符兜底（[vector_store.py:95](src/rag/vector_store.py#L95)），检索时这些占位素材（`achievements #0`）被召回混入 `reranked_context`，**污染 writer 输入**。
3. Writer 拿到垃圾素材 → 生成空/残篇回答 → 评审 completeness 打低分 → 触发修订 → 每次修订仍拿到同样污染素材 → **修订 3 轮死循环**，总分 6.5/25。

**解决方案**：
1. [chunker.py](src/rag/chunker.py)：修正三目优先级，改为始终拼接句子、句末无标点时补句号，**杜绝空 chunk**。
2. [retriever_node.py](src/agents/retriever_node.py) `fusion_node`：过滤 `{collection} #{N}` 占位/空 content 素材（双保险，防旧索引残留）。
3. 重建 ChromaDB 索引（重新上传简历，`vs.reset()` + 新 chunker 重新分块）。

**验证**：
- chunker 修复后 84 个 chunk 全非空（之前 31 个空）
- 重建后 achievements 42 条全部真实（占位 0）
- 完整工作流跑 2 次："AI Agent 项目" → 回答 1303/1525 字、总分 25.0/24.3、修订 0/2 轮 ✅
- 修复前同问题：回答 0 字、总分 5.0-6.5、修订 3 轮 ❌

---

## 2026-08-01

### 案例 1：简历解析项目"出不来"（只解析出 1 个，实际 3 个）

**现象**：上传"刘汪洋简历 全栈.docx"后，项目只解析出 1 个，视觉康复、西湖大学两个项目丢失。

**根因**：`_extract_projects_v2` 用**顺序互斥**的两种分割策略：
- 策略1（`项目名 + 4空格 + 日期`）分出 2 块（ResuMatch | 西湖大学）
- 策略2（`项目名 | 角色`）只在块数 `<=1` 时才运行 → **永远不执行**
- **视觉康复**（`名称 | 角色 公司` 格式）被吞进 ResuMatch 块 → 丢失

次要根因：
- 合并逻辑把「西湖大学张紫阳实验室」（带独立日期 `2024.03-2024.09`）误判为上一块延续 → 也被吞
- 视觉康复名称未清理 `| 角色 公司`，角色未提取
- ResuMatch 时间 `2026.05 – 至今` 未被正则捕获
- 技术栈正则把整句成果误抓成技术栈

**解决方案**（[src/rag/parser.py](src/rag/parser.py)）：
1. 两种分割边界合并为**单一交替正则**，任意匹配即切分
2. 合并逻辑加保护：带项目头信号（时间/角色/`|`）的块不再被误吞
3. 从 `名称 | 角色 公司` 首行拆分角色
4. 时间正则兼容 `至今` 格式
5. 技术栈正则加中文词尾负向断言，避免误抓"6项RAG增强技术："

**验证**：全栈简历从 1 项目 → 3 项目；其余 5 份简历回归正常（无退化）。

---

### 案例 2：简历上传 500 —— 嵌入模型 bge-small-zh 缓存不完整

**现象**：`POST /resume/upload` 返回 500，`_path_isfile: path should be string... not NoneType`。

**根因**：`BAAI/bge-small-zh` 的 HuggingFace 本地缓存**被拆散**：
- `modules.json` 引用了 `1_Pooling/` 子目录，但缓存里**缺失**（加载 Transformer 时把本地路径当 repo_id 去 `snapshot_download` → `HFValidationError`）
- 权重文件是 `pytorch_model.bin`，触发 torch 2.5.1 的 CVE-2025-32434 安全检查拒绝加载

**解决方案**（本地模型缓存，非代码）：
1. 补建缺失的 `1_Pooling/config.json`（512维 mean pooling 配置）
2. 补齐 `tokenizer.json / tokenizer_config.json / vocab.txt / special_tokens_map.json`
3. 从 PR snapshot 复制 `model.safetensors` 到完整 snapshot，删除 `pytorch_model.bin`（safetensors 安全格式绕开 torch.load 检查）

**验证**：`get_embedder().encode()` 成功返回 (2, 512)；上传 API HTTP 200，84 文档入库。

---

### 案例 3：React 前端点击"提交文件"没反应

**现象**：简历上传页点击上传区域，没有任何反应（不弹出/弹出后立刻消失，无法选文件）。

**根因**：`<input type="file">` 嵌在可点击的 `<div onClick={() => inputRef.current?.click()}>` 内。程序化调用 `input.click()` **冒泡**回 div 的 onClick，再次触发 `input.click()`，形成**递归重开**。用户选完文件对话框立刻重开，`change` 事件无法正常完成。实测点一次弹出 **5 个叠加的文件选择框**。

**解决方案**（[frontend/src/components/shared/FileUpload.tsx](frontend/src/components/shared/FileUpload.tsx)）：
给 `<input>` 加 `onClick={(e) => e.stopPropagation()}`，阻止点击冒泡回 wrapper。

**验证**：点上传区域只弹 1 个文件选择框；上传后解析结果正常渲染（技能27/项目3/成果3/教育2）。

---

### 案例 4：项目-JD 匹配引擎从 ChromaDB 读到空技术栈

**现象**：`/match/projects` 返回的每个项目 `tech_overlap=0`、`matched_tech` 空，技术交集匹配失效。

**根因**：项目匹配引擎从 ChromaDB `projects` 集合读项目，但该集合存的是**被 ParentChildChunker 切碎的 child chunk**（每个 chunk 只是碎句），`content` 里没有完整的技术栈/成果行，无法还原结构化项目。

**解决方案**（架构级）：
1. 新建 [src/features/profile_store.py](src/features/profile_store.py)：结构化简历档案/项目库 JSON 持久化（`data/profile.json`）
2. [routes.py](src/api/routes.py) 上传时 `ProfileStore.save(profile)` 落盘（含完整结构化 projects）
3. [project_matcher.py](src/features/project_matcher.py) `_load_projects` 改为**优先读 ProfileStore**（可靠），ChromaDB 仅作降级兜底

**验证**：`/match/projects` 正确读取 3 个结构化项目，ResuMatch AI 74 分（技术交集 100%）正确排第一。

---

### 案例 5：STAR 回答"张冠李戴"—— 医疗项目混入 ResuMatch AI 多Agent 技术

**现象**：介绍"医疗随访系统的 AI Agent 工作"时，回答前半段是视觉康复（真实），后半段却把 ResuMatch AI 的"3路并行检索/Fusion/STAR Writer/评审回环"安到了医疗项目上，且这些内容在医疗项目里不存在（编造/混入）。

**根因**（已复现）：
- 问题里"AI Agent"关键词语义命中了 **ResuMatch AI 的多Agent技术素材**，检索的 `reranked_context` 混入了两个项目的素材
- [prompts.py:27-38](src/core/prompts.py#L27-L38) 的 `STAR_USER_TEMPLATE` 把**所有** `reranked_context` 不加项目区分地塞给 writer
- 引用标注只到 `[来源: achievements]` **集合粒度**，不区分具体项目，writer 无法感知"这是另一个项目的素材"
- 评审环节同样把所有 context 混在一起验证，无法发现张冠李戴
- **深层**：视觉康复素材的 ChromaDB `source_text` 元数据被污染（误标为 ResuMatch），导致项目归属推断错误

**解决方案**（三层修复）：
1. **writer 侧**（[src/core/prompts.py](src/core/prompts.py)）：
   - `STAR_SYSTEM_PROMPT` 增加「项目归属约束」：只能使用与问题项目一致的素材，禁止跨项目混用技术/成果
   - `_infer_project_name()` 重写：优先按 **content 内容**匹配项目关键词（防 source_text 污染），再回退 metadata/source_text
   - `build_star_prompt()` 对每条素材加 `[项目: xxx]` 前缀标注
2. **检索侧**（[src/agents/retriever_node.py](src/agents/retriever_node.py)）：
   - `fusion_node` 调用新增的 `_boost_targeted_project()`：检测问题提到哪个项目，**目标项目素材提权 +2**，非目标已知项目素材**降权 -3 并从上下文剔除**
   - 项目素材不足时从 ChromaDB 补充召回目标项目素材
3. **验证**：问医疗问题时，素材全部归属「视觉康复」，回答聚焦语音转文字/多端协同，**不再含 ResuMatch 或 3路并行技术**；writer 诚实指出"并非独立 AI Agent 项目"。

**验证**：
- 问医疗问题 → 8 条素材全为视觉康复，回答含 ResuMatch=False、含3路并行=False ✅
- 问 ResuMatch → 素材聚焦 ResuMatch，回答不再误用医疗背景 ✅
- Python 编译通过 ✅
