# 04-30-research-external-projects

## Goal

对外部浏览器自动化/MCP/验证码相关项目进行系统调研，形成可落地的启示与路线建议，支撑 Mimicry 的中长期产品与技术决策。

## What I already know

* 已有一份初步调研文档：`docs/research/external-projects-analysis.md`，覆盖 5 个项目与路线建议。
* 项目关注点包含：MCP 能力扩展、反指纹/逆向工具链、平台化与队列、验证码处理、VNC 画面回传。

## Assumptions (temporary)

* 需要补齐更多“对标项目”的对比表与功能覆盖面。
* 需要更明确可执行的短中长期路线分解与优先级。

## Open Questions (resolved)

* 交付物形态：用户 2026-04-30 确认 = 对标矩阵 + 工程实践锐评 + 逐项目深度档案 + 可落地需求清单（短中长路线）
* 调研深度：用户确认允许克隆并阅读关键源码 → 5 个仓库已克隆到 `examples/external/`（gitignored）

## Requirements

* 形成可复用的调研产物（便于后续产品/研发引用）
* 对每个外部项目产出深度档案（含 ≥3 个带 `file:line` 引用的 code pattern）
* 综合产物含工程亮点提炼 + Mimicry 工程短板锐评 + 反向决策清单（不做的事）

## Acceptance Criteria

* [x] 覆盖 MCP 相关、验证码处理、平台化/队列三类方向的对标结论
* [x] 提供可执行的短/中/长路线建议
* [x] 5 个项目均有独立深度档案（research/01-05）
* [x] Mimicry 工程现状自审独立成档（research/00）
* [x] 综合稿覆盖对标矩阵 + 工程亮点提炼 + 锐评 + 反向决策 + 风险清单

## Definition of Done

* [x] 研究结论已落盘到任务 `research/` 目录
* [x] PRD 与研究结论一致
* [x] 综合稿替换了旧版 `docs/research/external-projects-analysis.md`

## Out of Scope (explicit)

* 实际功能开发与代码实现 — 路线表里的所有 S/M/L 任务都需要单独建任务实施

## Technical Notes

* 任务 `research/` 产物：
  * `00-mimicry-engineering-audit.md` — Mimicry 工程现状自审
  * `01-camoufox-mcp.md`
  * `02-headlessx.md`
  * `03-camoufox-reverse-mcp.md`
  * `04-playwright-captcha.md`
  * `05-webai2api.md`
* 对外稿：`docs/research/external-projects-analysis.md`
* 外部仓库克隆：`examples/external/{camoufox-mcp, HeadlessX, camoufox-reverse-mcp, playwright-captcha, WebAI2API}` — 已 gitignore
