# 错误案例记录（Bug Log）

> **本项目强制规则（见 [CLAUDE.md](CLAUDE.md) 第 6 节）：每次出现 bug 必须记录到本文件，
> 并与修复代码同一提交入库。**
>
> 标准格式（现象 → 根因 → 解决方案 → 验证）：
> ```
> ### 案例 N：<一句话标题>
> **现象** / **根因** / **解决方案** / **验证**
> ```
> 低级错误（拼写/缩进/单行）用精简单行格式，同编号体系。
> 根因分析优先于修复方案——记录的目的是让同类问题可按图索骥。
> 新案例插在对应日期段的最上方，案例编号全局递增。

---

## 2026-09-29

### 案例 20：上传文件名路径穿越 + 同名覆盖（安全缺陷）

**现象**：`POST /resume/upload` 的文件落盘直接用 `file.filename` 拼路径：文件名含 `../` 可把文件写到 `data/resumes/` 之外（如覆盖项目源码/配置）；同一简历二次上传同名文件会静默覆盖旧文件（无任何提示）。

**根因**（[routes.py](src/api/routes.py) 上传路径）：`file_path = upload_dir / file.filename`——浏览器/构造请求方可任意指定 filename，Path 拼接对 `../` 无防护；且未做存在性检查。属于"信任了不可信输入"的经典注入面。

**解决方案**：
1. 文件名消毒：只保留安全字符（字母数字/下划线/连字符/点/中文），其余替换为 `_`；剥离开头 `.`（防隐藏文件）；截断 120 字符
2. 落盘前检查存在性：冲突时追加 6 位随机后缀（`简历_abc123.pdf`），历史文件不再被覆盖

**验证**：上传 filename=`../../evil.py` → 落盘为 `data/resumes/___evil.py`（消毒后，位于 resumes/ 内）；同名二次上传 → 生成 `_xxxxxx` 后缀新文件，旧文件完好。

---

### 案例 19：/form/fill 指示 LLM 编造默认值（违反 LLM 边界）+ 500 裸抛 + 事件循环冲突

**现象**（一处主缺陷 + 两处连带，同一次审查发现）：
1. `/form/fill` 的 prompt 明确写着「档案没有的，填入合理默认值如民族→汉族、政治面貌→共青团员」——这正是 [CLAUDE.md](CLAUDE.md) LLM 边界表里 ❌「编造/推断缺失信息」「生成简历中没有的内容」的教科书案例。档案里没有的信息被 LLM 编一个"合理"值直接 auto_fill，网申表单里悄悄填上假数据。
2. 同端点 LLM 失败直接 `HTTPException(500)`——违反退路原则（前端 popup 有本地规则匹配兜底，后端 500 反而把兜底路径堵死）。
3. memory.py 的 `_trigger_compression` 在同步方法里 `asyncio.new_event_loop()` 直接驱动 `chat_sync`——上轮连接池改造后，httpx AsyncClient 绑定主循环，跨循环使用会抛 RuntimeError（潜伏雷：48K 压缩一旦触发必炸）。

**根因**：
1. prompt 演化过程中为"提高填充率"加入了默认值指示，与项目最高约束（LLM 边界）直接冲突却无人对齐——**CLAUDE.md 边界表没有同步进 /form/fill 的 prompt**；且仅靠 prompt 约束本身不可靠，无代码级防线
2. 退路缺失源于早期直抛习惯
3. 事件循环冲突是连接池改造（v21，案例 9 根治）的连带影响：共享连接池后，任何"自建循环调 chat_sync"的旧代码都成了雷——**改造共享资源时必须全量排查旧用法**，这是本次的架构级教训

**解决方案**（[routes.py](src/api/routes.py)、[memory.py](src/core/memory.py)）：
1. prompt 重写为「LLM 使用边界」约束：只映射不编造、档案没有的留空、选项严格取原文、value 需可在档案中回溯
2. **后处理强制执行**：LLM 返回后逐条检查 value 是否存在于档案文本——不在的降级 `review`（人工确认）。提示词可被 LLM 无视，代码检查不会
3. LLM 失败降级返回空计划 + `degraded: True`（前端已有本地匹配兜底，不再 500）
4. 顺带落地 SPEC 3.2「缓存系统」：key=表单结构+档案内容指纹（llm_cache），相同表单+相同档案秒回，上传新简历指纹变即自然失效
5. memory.py 压缩改线程池执行（独立线程自建循环，与主循环互不干扰，60s 超时）

**验证**：
- 档案无民族信息时请求含"民族"字段 → value 为空、action=skip/review，不再出现"汉族"
- 后处理防线：注入不在档案的 value → action 被强制 review
- LLM 不可用（无 key）→ 200 + `degraded: True`，前端走本地匹配
- 同一表单结构二次请求 → `cached: True` 毫秒级返回

---


### 案例 18：「asyncio.gather 并行检索」是假并行——协程切换救不了同步阻塞

**现象**：SPEC/README 宣称"3路并行检索，总耗时 = max(单路) 而非 sum"。实际观测（fusion_stats 的 agent_timing）：三路耗时接近**累加**而非取最大，且检索期间整个 FastAPI 服务对其他请求无响应（事件循环被卡死）。

**根因**（asyncio 并发模型 + Python GIL 的两层错位）：

1. `asyncio.gather` 只调度**协程**。协程只在 `await` 点让出控制权——三个 agent 函数虽然标了 `async`，但内部全是**同步调用**：`vs.search()`（Milvus/Chroma 查询）、`embedder.encode()`（torch 推理）、`graph.expand_query()`（纯 CPU 正则）。同步段一旦开始执行，事件循环无法打断，只能等它跑完。
2. 结果：三路"并行"实际是**串行**——A 跑完才轮到 B。`parallel_elapsed_ms ≈ sum(agent_timing)`。
3. 更糟的是 torch 推理直接跑在**主事件循环线程**上：一次 embedding 批推理（几十 ms 到秒级）期间，所有并发 HTTP 请求、SSE 心跳全部冻结。

**为什么一直没被发现**：单请求场景下"串行跑完"与"并行跑完"最终结果相同，只是慢；只有 (a) 看 agent_timing 数字、(b) 并发压测、(c) SSE 流式时才暴露。宣传语与实现的偏差属于**静默性能缺陷**。

**解决方案**（[src/agents/retriever_node.py](src/agents/retriever_node.py)）：
1. 三个 agent 的同步核心（检索循环、embedding、精排、图谱展开）整体包 `asyncio.to_thread(...)`——丢进线程池，事件循环立刻解放
2. to_thread 默认线程池并发三路真正并行（torch 推理在 Python 层释放 GIL，线程级并行有效）
3. 语义缓存 embedding 查询（routes 侧）同样包 to_thread

**验证**：fusion_stats 的 `parallel_elapsed_ms` 从 ≈ sum(agent_timing) 降为 ≈ max(agent_timing)；检索期间并发请求不再冻结。

**教训**：`async def` + `asyncio.gather` **不等于**并行。凡内部含同步阻塞（DB 查询、模型推理、requests）的"async"函数，要么 `to_thread`/`run_in_executor`，要么换原生异步客户端——否则 gather 只是排队。

---

### 案例 17：安装 milvus-lite 连环破坏 pandas（numpy 2.x ABI 断裂）

**现象**：`pip install pymilvus milvus-lite` 成功，但随即任何 `import pandas` 全灭：

```
ValueError: numpy.dtype size changed, may indicate binary incompatibility. Expected 96 from C header, got 88
```

连带症状：安装中途还出现过两次 `JSONDecodeError: Unterminated string`（PyPI 元数据下载中断）和 `THESE PACKAGES DO NOT MATCH THE HASHES`（缓存损坏），均为同一网络/缓存不稳链条的表象。

**根因**（依赖链，非表面错误）：
1. milvus-lite 3.x → pyarrow/faiss-cpu 新版 → **numpy 2.4.6** 被拉入
2. 环境里的 pandas 2.1.1 是 **numpy 1.x ABI** 编译的 C 扩展 → 二进制不兼容
3. 项目 requirements.txt 原本钉死 `numpy==1.24.3`，但直接 pip install 单独装包时**绕过了 requirements 的联合解析**，pip 选了满足新包的 numpy 2.x，旧包的 ABI 约束无法表达

**解决方案**：
1. 立即修复：`pip install --no-cache-dir "numpy>=1.26,<2.0.0"`（pandas 2.1.1 与 1.26.x ABI 兼容）
2. 根治（[requirements.txt](requirements.txt)）：`numpy==1.24.3` → `numpy>=1.24.3,<2.0.0` 并加注释说明 pandas 2.1.1 的 ABI 约束，防止下次整装时再次被 milvus-lite 拉到 2.x
3. 教训：往已锁版本的环境里**单独追加**新依赖时，必须回查既有 C 扩展包的 ABI 兼容窗口，requirements 的约束要在同一次解析里生效

**验证**：`import numpy, pandas, pymilvus, milvus_lite` 全部通过；全量测试 28/28。

---

### 案例 16：Milvus COSINE 与 ChromaDB 的 distance 语义相反（迁移即翻车点）

**现象**：Milvus Lite 迁移后首轮冒烟测试，检索结果排序看起来正常但数值可疑——直接照搬 ChromaDB 的 `score = 1.0 - distance` 公式后，**所有素材分数塌到接近 0 且次序含义颠倒**（最相关的素材反而拿最低分）。

**根因**（度量语义差异，跨库迁移的经典坑）：
- ChromaDB `hnsw:space=cosine` 返回的是**余弦距离**（0=相同，2=相反）→ 相似度 = 1 - distance
- Milvus `metric_type=COSINE` 返回的是**余弦相似度本身**（1=相同，-1=相反，越大越好）→ 透传即可
- 两个库的"distance"字段含义相反，套同一个转换公式等于把排序镜像

上层 `fusion_node` 按 `(vote_count, score)` 排序、`_boost_targeted_project` 做 ±0.3/−0.5 加权——score 语义一反，整个融合层全废且**不报错**（静默质量劣化，最危险的一类）。

**解决方案**（[src/rag/milvus_store.py](src/rag/milvus_store.py)）：
1. Milvus 路径 `score` 直接透传（裁剪到 [-1,1] 防越界）
2. ChromaDB 降级路径维持 `1 - distance`
3. 模块头注释显式写明两库口径差异，防止后人"统一"公式

**验证**：冒烟测试断言 top-1 命中 PaperPilot（score 0.884）且分数单调递减；两后端同一查询分数同序。

---

### 案例 15：9 个向量存储测试长期失败——type 单复数契约漂移 + fixture 不幂等

**现象**：`pytest tests/` 稳定 9 failed / 10 passed 已数轮迭代，失败集中在 test_vector_store（8个）和 test_parser::test_to_documents（1个）。因"测试一直红着"被当作背景噪音，无人定位。

**根因**（两层，均在测试侧，实现从未错）：
1. **type 契约漂移**：parser `to_documents()` 实际产出 `metadata.type` 为复数（`"skills"/"projects"/"achievements"`，与集合名对齐），测试 fixture/断言用的却是旧单数（`"skill"/"project"/"achievement"`）。`index_documents` 按 type 分桶 → 单数 type 全部落入 grouped 的空桶 → **一个都没写进去** → count=0、search 空、后续全红
2. **fixture 清理缺集合**：teardown 只删 4 个集合（skills/projects/achievements/education），漏了 `project_docs`——首个用例残留的 project_docs 计数污染后续用例的 `get_collection_info` 断言

**解决方案**：
1. [tests/test_vector_store.py](tests/test_vector_store.py)：fixture 的 type 改复数（对齐 parser 真实输出）；teardown 改 `store.reset()` + 全集合清理
2. [tests/test_parser.py](tests/test_parser.py)：`test_to_documents` 断言改复数
3. 迁移顺带把 fixture 升级为 **Milvus/ChromaDB 双后端参数化**——同一套用例在两个后端各跑一遍，接口兼容性从此有回归防线（本次就靠它抓出了 ChromaDB `n_results=0` 抛 TypeError 的空集合边界，已加卫语句修复）

**验证**：修复前 9 failed / 10 passed → 修复后 **28 passed / 0 failed**（14 用例 × 2 后端 + parser 10 用例）。

---

## 2026-09-29

### 案例 14：多轮对练的会话历史每轮被覆盖（追问上下文恒为空）

**现象**：面试对练第 2 轮起，AI 回答质量明显弱于第 1 轮——不记得前面问过什么，追问失去连贯性。`session["history"]` 看似在写入，但下一轮读到的永远是上一轮的那一条。

**根因**（数据流层面的拷贝语义）：

[redis_store.py](src/core/redis_store.py) 的 `RedisSessionStore.get()` 每次调用都**反序列化出一个全新的 dict**（Redis 路径 `json.loads(raw)`，内存降级路径同样返回引用副本的语义），而 `set()` 是整条 JSON 覆盖写。调用链：

```
routes.py  mock_interview_next:
  session = session_store.get(id)      # ← 新对象 A（含 history）
  session["round"] += 1
  session["history"].append({...})     # ← 只写进 A
  await _generate_mock_answer(...)     # ← 中间有 await，期间 A 未被持久化
  session["history"][-1]["answer"] = ai_answer
  session_store.set(id, session)       # ← 写回，A 落盘
```

表面看 `set` 在最后，逻辑闭合。**但真正的缺陷是：生成回答的 `_generate_mock_answer()` 只把当前 `question` 写进 prompt，从不读取 `session["history"]`。** 所以无论 history 写得多完整，回答这一侧都拿不到上下文——同一份 history 只被 `/mock/suggest`（AI 生成追问）读取过，回答侧从未使用。history 对「回答」而言只是被存下来给前端展示，多轮对练的"追问"实际上是 N 次互相独立的单轮问答。

次要缺陷：`session_store.get()` 返回的是**值拷贝**，若在 `get()` 与 `set()` 之间存在并发请求（同一 session 的两个 `/mock/next`），后写入者会整条覆盖前者——`set` 是覆盖写而非合并写，没有乐观锁。

**解决方案**（[src/api/routes.py](src/api/routes.py)）：

1. `_generate_mock_answer()` 新增 `history` 参数，把 `history` 中**已完成**的轮次（问题 + AI 回答，各截断 500 字，最多最近 5 轮）拼成「前面几轮的问答」注入 prompt——这是本案例的实质修复
2. `/mock/next` 传入 `session["history"][:-1]`（排除当前这轮，其 `answer` 尚未生成，不应出现在 prompt 里）
3. **LLM 缓存 key 补入 `history_text`**——否则同一句话在不同轮次下会命中同一个缓存条目、返回脱离上下文的旧答案（这是修完第 1 点后立刻会踩的坑）
4. 会话读改写路径加注释说明「`get` 返回新对象，改后必须 `set` 回写」，避免后续再踩拷贝语义

**验证**：模拟 3 轮连续追问（同一 session_id），第 2/3 轮 prompt 中确认包含前序问答；AI 回答能正确指代前文。缓存侧验证：同一问题在第 1 轮与第 3 轮分别调用，`cache_payload` 不同、未命中同一缓存条目。

---

### 案例 13：`/interview/stream` 完全不检索——同一次提问两条链路结果不一致

**现象**：React 面试页（「面试模拟」单次问答）走 `POST /api/v1/interview/stream`，回答明显比 `/interview/answer` 空洞——不引用简历素材、不体现具体项目，像是一般性泛泛而谈。同一个问题换个入口问，答案质量差一截。

**根因**（入口参数缺失引发的连锁降级）：

[graph.py:44](src/agents/graph.py#L44) 的 `should_retrieve()` 判断依据是 `state["user_profile"]` 里有没有 `indexed_docs` / `collections`：

```python
if profile.get("indexed_docs") or profile.get("collections"):
    return "retrieve"
```

而两个入口装载画像的方式不一致：

| 端点 | 是否传 `user_profile` | 后果 |
|---|---|---|
| `/interview/answer` | ✅ 读了 ChromaDB 拼出 `indexed_docs` | 正常检索 |
| `/interview/stream` | ❌ **根本没传** | 见下 |

`user_profile` 为空触发了**三层连锁降级**（每一层单独看都"合理"，叠加起来就是检索全废）：

1. **`should_retrieve` 落到问题类型兜底**——问"介绍一下你的项目"时 `qtype=project_followup` 侥幸返回 "retrieve"；问"你最大的优势是什么"（`general`）直接返回 **"skip"**，检索完全跳过
2. **Planner 画像微调失效**——[planner.py:133](src/agents/planner.py#L133) 的 `skills_count`/`projects_count` 全为 0，[第 95 行](src/agents/planner.py#L95) 的分支把握把 `active_retrievers` 削成 `["semantic"]`，关键是**后续"有数据就补回 keyword/graph"的两个兜底也一并失效**（因为它们同样以 `skills_count > 0` 为条件）
3. **semantic 路的画像增强失效**——[retriever_node.py:69](src/agents/retriever_node.py#L69) 的 HyDE 摘要依赖 `user_profile["name"]`，空画像时 `summary=""`，HyDE 假设文档质量下降

**解决方案**（[src/api/routes.py](src/api/routes.py)）：

1. 抽出 `_load_user_profile()` 统一装载画像——**同时**取 ProfileStore 的结构化字段（供 Planner 计数 + HyDE 摘要）与 ChromaDB 的 `indexed_docs`/`collections`（供 `should_retrieve` 判断），两份数据缺一不可，之前 `/answer` 只装了后者
2. `/interview/answer` 改调该函数（行为对齐，去掉重复代码）
3. `/interview/stream` 在**进入事件生成器之前**装载画像并传入——不能放进生成器内 `await`，那会拖慢 SSE 首字节并破坏流式体验
4. 装载过程分两段独立 try/except（错误隔离），任一份取不到不影响另一份，最终可能返回空 dict（未上传简历时的合法状态）

**验证**：同一问题分别打两个端点，planner 日志中 `skills_count`/`projects_count` 均非 0、`active_retrievers` 为三路；`should_retrieve` 返回 "retrieve"；SSE 事件流中出现 `parallel_retrieval` 节点且 `total_docs > 0`。

---

### 案例 12：`project_docs` 集合只写不读——档案页上传的项目资料从未进入面试回答

**现象**：在档案页按项目上传了资料文档（md/txt/docx/pdf），接口返回成功、ChromaDB `project_docs` 集合计数正常增长，但面试回答中**从不引用这些资料**，仍只基于简历里的技能/项目行作答。

**根因**（写入路径与读取路径的集合列表不同步）：

- **写入**：[routes.py](src/api/routes.py) `POST /project/{project_name}/docs` → 分块存入 `project_docs` 集合，metadata 带 `project_name` ✅
- **读取**：[retriever_node.py:79](src/agents/retriever_node.py#L79) 三路检索的集合列表硬编码为 `["skills","projects","achievements","education"]`——**没有 `project_docs`**；fusion 的 `retrieved_*` 分类同样没有它

`project_docs` 只在 `_generate_mock_answer`（面试对练的单次 LLM 路径）里被检索过，**多 Agent 工作流（`/interview/answer`、`/interview/stream`）从来没读过它**。而 SPEC 第 5 节项目简历明确写了「面试回答自动检索该项目文档基于真实资料作答」——该承诺只在一条链路上成立。

次要问题：[prompts.py](src/core/prompts.py) 的 `_infer_project_name()` 项目归属推断只看 content / `metadata.name` / `source_text`，而 `project_docs` 的归属字段叫 `project_name`——两者都对不上，即便把素材捞进上下文，也会丢归属标注（案例 5 的张冠李戴风险）。

**解决方案**：

1. [retriever_node.py](src/agents/retriever_node.py) `semantic_agent` 检索集合加入 `project_docs`，与其余素材一同参与投票/精排/融合
2. `fusion_node` 新增 `retrieved_project_docs` 分类
3. 三处归属匹配的 haystack 补上 `metadata.project_name`：`_boost_targeted_project` 的目标项目识别、非目标项目剔除、项目素材补充召回
4. [prompts.py](src/core/prompts.py) `_infer_project_name()` 新增**最高优先级分支**——`project_docs` 自带 `project_name`，是最可靠的归属来源，直接采用，不再走关键词猜测

**验证**：上传该项目资料文档后提问相关问题，`reranked_context` 中出现 `collection=project_docs` 的素材且带正确 `[项目: xxx]` 标注；回答引用了文档中简历未记载的细节。

---

## 2026-09-28

### 案例 11：全量依赖无法安装（连锁版本冲突 + 上限缺失 + 弃用包残留）

**现象**：解决案例 10 的编码问题后，`pip install -r requirements.txt` 报 `ResolutionImpossible`：

```
ERROR: Cannot install anyio>=4.0.0 and fastapi==0.104.1 because these package versions have conflicting dependencies.
    The user requested anyio>=4.0.0
    fastapi 0.104.1 depends on anyio<4.0.0 and >=3.7.1
```

**根因**（三层，pip 一次只暴露一层，需逐层解开）：

1. **`anyio` 与 fastapi 硬互斥**（requirements.txt:59）：fastapi 0.104.1 经 starlette 0.27 要求 `anyio<4.0.0`，而文件里显式写了 `anyio>=4.0.0`——两个区间交集为空，任何解法都无解。且**项目源码从不 `import anyio`**（仅 fastapi/starlette 内部使用），这条声明是无人使用的多余约束。
2. **`pydantic` 钉死导致 langchain 线不可用**（requirements.txt:7）：`pydantic==2.5.0`，但 `langchain-core` 0.3.x 全系要求 `pydantic>=2.7.4`。注意 pip 的报错只显示了 `anyio`，**pydantic 冲突是解开第一层后才会浮出的第二层**。
3. **`langgraph` 无上限跨大版本**（requirements.txt:11）：`langgraph>=0.2.0` 无上界，pip 会解析到 **1.2.12**——1.x 要求 `langchain-core>=1.4.7`，与项目验证过的 0.2–0.6 线（`StateGraph` / `MemorySaver` / `add_messages`）不在同一代，存在 API 断裂风险。

附带问题：`streamlit==1.28.1` 残留在依赖清单中，但 CLAUDE.md 与 SPEC.md 均记载「Streamlit 已弃用」（前端已迁移 React），该依赖会平白拉入 8.4MB wheel 及其依赖树。

**解决方案**（[requirements.txt](requirements.txt)）：
1. `pydantic==2.5.0` → `>=2.7.4,<3.0.0`（先验证代码用法：仅 `BaseSettings` / `model_config` / 一个 `class Config:`，pydantic v2 各版本均兼容）
2. `langgraph>=0.2.0` → `>=0.2.0,<1.0.0`（加注释说明上限理由）
3. `anyio>=4.0.0` → `>=3.7.1,<4.0.0`（收敛到 fastapi 允许区间）
4. 删除 `streamlit==1.28.1`，并清理弃用痕迹：删除 `app.py` / `Dockerfile.streamlit`，移除 `.env.example` 的 `STREAMLIT_HOST/PORT`（[README.md](README.md)、[SPEC.md](SPEC.md)、[TECH_STACK_ANALYSIS.md](TECH_STACK_ANALYSIS.md) 的现存需求表述同步改为 React；历史变更日志保留原文）

**验证**（实际装机结果）：

| 包 | 装后版本 | 预期 |
|---|---|---|
| langgraph | 0.2.35 | ✅ 落在 0.x |
| langchain-core | 0.3.86 | ✅ |
| pydantic | 2.13.5 | ✅ 已脱离 2.5.0 |
| anyio | 3.7.1 | ✅ 回到 3.x |
| fastapi | 0.104.1 | ✅ 未动 |

导入自检通过（`langgraph.graph.StateGraph` / `checkpoint.memory.MemorySaver` / `graph.message.add_messages` 全部可用，证明未跨大版本）。附带两条告警非错误：`LangChainPendingDeprecationWarning`（langgraph 内部）、`fitz` API 弃用提示（PyMuPDF 旧名，仍可用）。

**教训**：requirements.txt 中「显式声明但代码未使用」的包（anyio）和「无上界的核心框架」（langgraph）是依赖地狱的两个典型来源——前者制造无解冲突，后者让 CI 与本地静默漂移到不同大版本。

---

## 2026-09-28

### 案例 10：`pip install -r requirements.txt` 报 UnicodeDecodeError（GBK 解码失败）

**现象**：在中文 Windows 上执行 `pip install -r requirements.txt`，未下载任何包即崩溃：

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x96 in position 1059: illegal multibyte sequence
  File ".../pip/_internal/utils/encoding.py", line 34, in auto_decode
      return data.decode(
```

**根因**：`requirements.txt` 含中文注释（`# Redis (会话持久化 + LLM缓存)`），文件实际是合法 UTF-8，但**既无 BOM、也无 PEP 263 编码声明**。pip 的 `auto_decode()`（[encoding.py:20-36](.venv/Lib/site-packages/pip/_internal/utils/encoding.py#L20-L36)）解码顺序为：

1. 匹配 BOM（`BOMS` 表）→ 无
2. 扫前两行找 `coding[:=]\s*([-\w.]+)` 声明 → 无
3. 回退 `locale.getpreferredencoding(False)` → 中文 Windows 上是 **GBK**

GBK 解码 UTF-8 的中文字节即抛 `UnicodeDecodeError`。**与依赖版本、镜像源、网络均无关**，是纯编码链路问题——同一文件在 Linux/CI（locale 为 UTF-8）下不会复现。

**解决方案**（[requirements.txt](requirements.txt)）：首行加入 PEP 263 声明 `# -*- coding: utf-8 -*-`，使 pip 在第 2 步命中 UTF-8 分支，不再回退 GBK。

**验证**：直接调用 pip 自身的解码函数复现修复前后：

```python
from pip._internal.utils.encoding import auto_decode
auto_decode(open('requirements.txt','rb').read())
# 修复前：UnicodeDecodeError: 'gbk' codec ... position 1059
# 修复后：OK，解析出 74 行
```

**备份方案**（若其他带中文的配置文件（如 `-r` 引用的文件）遇到同类问题）：将文件改写为带 BOM 的 UTF-8，命中第 1 步分支。

---

## 2026-08-03

### 案例 9：JD 匹配简历增强 `resume_content` 偶发为空/极短

**现象**：JD 匹配的"针对性简历内容"功能时好时坏——`added_skills` 稳定返回，但 `resume_content` 有时为 0、有时 84 字、有时正常几百字。裸 LLM 调用返回 1381 字，但走 API 完整流程却返回空。

**根因**（逐层排查）：
1. 先在 `_safe_generate` 里用 `DeepSeekClient(timeout=150)` 新建独立 client → 同一 prompt 只返回 **26 字**（异常变短），而全局单例 `get_client()` 返回 499+ 字。**新建 client 实例会导致 DeepSeek 响应异常短**，必须用全局单例。
2. 即使改回全局 client，LLM 对同一 prompt 仍**偶发返回空/极短内容**（不稳定，非超时非异常，无错误日志），单次调用不可靠。

**解决方案**（[src/features/project_matcher.py](src/features/project_matcher.py)）：
1. `_safe_generate` **必须用全局单例 `self.client`（get_client）**，禁止新建 DeepSeekClient 实例
2. `generate_resume_content` 对空/过短结果（<50字）**重试最多 3 次**
3. `added_skills` 规则化计算（不依赖 LLM），LLM 失败仍返回

**验证**：修复后 API 实测返回 640 字完整内容——增强后技术栈（原有技能全保留 + DeepSeek 建议补充）+ 项目描述增强（LangGraph/HyDE/ChromaDB），量化数据来自简历真实内容。

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

> **后续注记（v22 清理）**：本案例描述的"改用 run_interview_workflow"实际落地为
> `_generate_mock_answer` 单次 LLM 调用（对练场景取低延迟），`MockInterviewEngine`
> 始终零调用方，已随 v22 死代码清理删除。

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
