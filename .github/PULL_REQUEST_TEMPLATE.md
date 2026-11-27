## 这个 PR 做了什么

<!-- 一句话说明目的 -->

## 关联 Issue

<!-- 例如：Closes #12 -->

## 改动类型

- [ ] `feat` 新功能
- [ ] `fix` 缺陷修复（重要缺陷已同步记录到 BUG_LOG.md）
- [ ] `docs` 仅文档
- [ ] `refactor` 重构（不改变外部行为）
- [ ] `test` 测试
- [ ] `chore` 构建 / 依赖 / 工具链

## 影响范围

<!-- 勾选受影响的模块 -->

- [ ] `src/rag`（解析 / 检索）
- [ ] `src/agents`（多 Agent 编排）
- [ ] `src/api`（接口）
- [ ] `frontend/`（前端）
- [ ] `extension/`（浏览器扩展）
- [ ] `scripts/`（评测与工具）
- [ ] 文档

## 自查清单

- [ ] `pytest -q` 通过（36 项）
- [ ] 涉及前端时 `npx tsc --noEmit && npm run build` 通过
- [ ] 未提交 `.env`、密钥、真实简历等敏感内容
- [ ] 新增/修改了对外行为时，已更新 README 或 SPEC.md
- [ ] 修复缺陷时已补充 BUG_LOG.md 条目（含根因与验证结果）

## 验证方式

<!-- 说明你是怎么验证的：跑了哪个评测脚本、观察到什么指标变化 -->

```bash
# 示例
python scripts/eval_extraction.py
```

## 备注

<!-- 设计取舍、已知局限、后续计划 -->
