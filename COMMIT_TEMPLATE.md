# Conventional Commits 模板
# 用法：git commit（不带 -m 时自动打开本模板；或 `git commit --template=COMMIT_TEMPLATE.md`）
# 提交说明只保留「#」注释以下第一个空行之前的内容
#
# ── 格式 ─────────────────────────────────────────────
# <type>(<scope>): <subject>
#
# <body>
#
# <footer>
# ──────────────────────────────────────────────────────
#
# type（必选，小写）：
#   feat      新功能（用户可感知）
#   fix       缺陷修复
#   docs      仅文档（README/SPEC/TECH_STACK/BUG_LOG）
#   refactor  重构（不改外部行为）
#   perf      性能优化
#   test      测试新增/修正
#   build     构建/依赖（requirements、Dockerfile、package.json）
#   chore     杂务（不影响 src 与测试的其他改动）
#   style     格式（空格/分号/换行，不改语义）——本项目少用，格式问题随所属改动提交
#   ci        CI 配置
#   revert    回滚某提交
#
# scope（可选，小写，本项目固定集合）：
#   agents    LangGraph 工作流（src/agents/）
#   rag       检索管道（src/rag/）
#   api       FastAPI 路由/模型（src/api/）
#   core      基础服务（src/core/、src/config.py）
#   features  业务功能（src/features/）
#   frontend  React 前端（frontend/）
#   extension Chrome 扩展（extension/）
#   vector    向量库相关（milvus_store/vector_store）
#   deps      依赖（requirements.txt）
#   docker    容器/部署（Dockerfile、docker-compose.yml）
#   git       git 规范自身（.gitignore/.gitattributes/模板）
#
# subject（必选）：一行，≤50 字（中文按一字计），祈使句，不加句号
#   示例：feat(rag): HyDE 检索接入假设文档缓存
#
# body（可选）：空一行后写。什么改动 + 为什么（动机/背景），
#   引用 BUG_LOG 案例号或 SPEC 版本号，如「对应 BUG_LOG 案例 13」「SPEC v21」
#
# footer（可选）：空一行后写。
#   不兼容/重要变更：  BREAKING CHANGE: <说明>
#   关闭 issue：       Closes #12
#   历史案例引用：     Refs: BUG_LOG#13
#
# ── 多文件改动的拆分原则 ─────────────────────────────
# 一次提交 = 一个意图。典型拆分：
#   1. 功能改动（src/ + frontend/ + tests/）→ feat
#   2. 文档同步（SPEC/README/TECH_STACK）→ docs（单独提交，不与 feat 混）
#   3. 依赖/构建（requirements/Dockerfile）→ build
#   4. bug 案例记录（BUG_LOG.md 随对应 fix 一起提交）
# 例外：fix 的最小复现测试与修复代码同提交
