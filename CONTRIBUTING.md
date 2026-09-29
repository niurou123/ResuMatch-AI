# 贡献指南

## Git 提交规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

```bash
git commit              # 无 -m，自动打开 COMMIT_TEMPLATE.md
git commit -m "feat(rag): HyDE 检索接入假设文档缓存"
```

完整说明见 [COMMIT_TEMPLATE.md](COMMIT_TEMPLATE.md)（`git commit` 时自动加载）。

### type 速查

| type | 用途 |
|------|------|
| `feat` | 新功能（用户可感知） |
| `fix` | 缺陷修复（重要缺陷同步记 [BUG_LOG.md](BUG_LOG.md)） |
| `docs` | 仅文档（README / SPEC / TECH_STACK_ANALYSIS / BUG_LOG） |
| `refactor` | 重构（不改外部行为） |
| `perf` | 性能优化 |
| `test` | 测试新增/修正 |
| `build` | 构建/依赖（requirements.txt、Dockerfile、package.json） |
| `chore` | 杂务 |
| `revert` | 回滚某提交 |

### 本项目固定 scope

`agents` / `rag` / `api` / `core` / `features` / `frontend` / `extension` / `vector` / `deps` / `docker` / `git`

### 规则

1. subject 祈使句、≤50 字、不加句号
2. 一次提交 = 一个意图：功能改动、文档同步、依赖变更分开提交
3. body 引用依据：「对应 BUG_LOG 案例 N」「SPEC vX」
4. 架构级改动先更新 [SPEC.md](SPEC.md)（见 [CLAUDE.md](CLAUDE.md) 核心规则）
5. 不要提交 `.env`（只有 `.env.example` 入库）；`data/` 下运行时产物均已忽略

## 换行符

`.gitattributes` 已声明文本文件统一 LF；本仓库本地配置 `core.autocrlf=input`。`.bat`/`.cmd` 保持 CRLF。

## 分支模型

单人项目，主干开发：`main` 即开发线，重大重构/实验建 `feat/<名字>` 或 `fix/<bug 名>` 短分支，完成后合回。
