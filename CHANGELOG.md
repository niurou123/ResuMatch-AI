# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，
版本号使用 `vN` 递增序号（对应 `SPEC.md` 的变更日志）。

## [v34] - 2026-11-26

### Added
- 复合问题分解链路：`decompose` / `sub_parallel` / `synthesize` 三节点（fan-out & fan-in）
- 证据充分性闸门 `evidence_gate`，对缺失证据的子问题触发定向补充检索（Self-RAG 式回环）
- 扫描件 PDF 的 OCR 兜底（RapidOCR，惰性初始化、限页、可取更长的文本）
- 解析器整块文本结构化 `_normalize_blob_text`，识别 PDF 提取后挤在同一行的分区标题
- 六组可复现评测脚本与报告（字段提取 / 鲁棒性 / 检索消融 / 生成三档 / 分解 A/B / 表单填充）
- 论文与答辩材料生成工具链：`make_thesis_skeleton`、`check_thesis_format`、`verify_refs`、`make_kaiti_ppt`
- 项目治理文件：LICENSE(MIT)、SECURITY、CHANGELOG、CI 工作流、Issue / PR 模板

### Changed
- 前端整体改为白底黑字企业后台风格：纯白底 + 1px 细边框，主色 `#0b6bcb` 仅用于主按钮、
  当前菜单项与链接；布局对齐 vue-pure-admin（224px 侧边栏 + 48px 面包屑栏 + 铺满内容区）
- 字号整体放大：根字号 17px、正文 15px、页面标题 21px
- 英文分区别名扩充（professional experience / core competencies 等）

### Fixed
- `run_interview_workflow` 用 `astream` 返回状态增量，导致 `sub_questions` 等字段丢失（改用 `ainvoke`）
- `AgentState` 未声明分解相关字段，LangGraph 不为其建立状态通道
- 解析器对真实简历完全失效（外部语料成功率 0% → 83.3%）
- 思维链泄漏：`content` 为空时把 `reasoning_content` 当答案（数字可回溯率 0% → 100%）
- 模型判断 `"v4" in model` 误把 flash 归为推理模型

## [v30] - 2026-11-25

### Added
- 外部公开语料鲁棒性评测（CC0 / MIT，48 份，含 8 份扫描件）
- 参考文献回源核验工具（Crossref / arXiv 批量校验）

### Changed
- 模型切换到 `deepseek/deepseek-v4.1-flash`（commandcode 网关）
- 提示词改为 STAR 四段显式标签 + 数字原样引用硬约束

## [v9] - 2026-11-20

### Changed
- 界面去卡通化：移除 emoji 与高饱和渐变，统一标签与按钮样式

## [v3] - 2026-11-10

### Added
- LangGraph 多 Agent 并行架构：3 路并行检索 + 3 路并行评审 + 多数表决 + 修订回环
- 父子分块、中文嵌入、交叉编码器精排
- Chrome MV3 扩展：表单扫描、分区感知映射、一键填充
- 结构化档案与字段来源标注

## [v1] - 2026-11-01

### Added
- 项目初始化：FastAPI 后端骨架、简历解析器 v1、基础问答链路
