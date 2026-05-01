# 05-01-readme-clippy-style

## Goal

把 Mimicry 的 README.md 重写为类似 51hhh/Clippy 项目的 marketing 风格——突出已实现能力、视觉化呈现、克制不写 alpha 免责。同步更新 docs/README.zh-CN.md 中文镜像。**正确引用所有第三方依赖，标注许可证，加自动化工具法律免责，明确学习交流用途**。

## What I already know

- Clippy README 已读完：banner 居中 → 标语 → badges → 双语链接 → 一句话 elevator pitch → Screenshots → Features (bullet) → Install → Build from Source → Tech Stack 表 → Architecture (mermaid) → Project Structure → Development → Contributing → Credits → License
- Mimicry 现有 README.md 是 247 行，自标 alpha + 含 Roadmap，要用更"产品页"语气重写
- 现有 docs/README.zh-CN.md 中文版需同步重写
- Banner 用现有图标 src-tauri/icons/icon.png 或 app-icon.svg，深色背景 + 文字
- License 矛盾点：Mimicry 自己**没有 LICENSE 文件**（README L246 自承认），本任务不解决，只在 README 用语上避免说"MIT"
- 用户已对齐答案：英文主 + 中文镜像；marketing 风；突出 MCP/CLI；Features 详细；可视化 workflow + JSON

## Scope (in)

### Part A — README 内容
A1. 完整重写 README.md 为 Clippy 风格 marketing 文案
A2. 完整重写 docs/README.zh-CN.md（与 A1 1:1 对应）
A3. 顶部双语链接
A4. Banner 占位 docs/banner.png（**资产生成留给 Part B**）
A5. Features 部分至少覆盖：可视化 workflow、JSON 直驱、Camoufox 反指纹、三入口 Sidecar、MCP 52 工具、CLI Daemon、录制回放、Profile 隔离、Cloudflare captcha click solver、SQLite 持久化、自动更新、i18n
A6. Tech Stack 表
A7. Architecture mermaid 图（基于 docs/architecture.md 提炼）
A8. Quick start：仅 cargo tauri dev / build
A9. 详细开发命令一行带过指向 CLAUDE.md
A10. Credits 完整列出**所有运行时依赖**（pnpm 主依赖 + sidecar requirements + Rust 主 crate）
A11. **法律免责段（必须）**：参考 playwright-captcha 的 LEGAL DISCLAIMER 风格
A12. **学习交流用途声明**
A13. **License 风险标注**：依赖 Camoufox（MPL）、Playwright、playwright-captcha 拷贝代码（Apache-2.0）等

### Part B — Banner 资产
B1. 生成 docs/banner.png（基于 src-tauri/icons/icon.png + 标语，深色背景，1200x300 或类似尺寸）
B2. 路径：docs/banner.png
B3. **决策**：用 ImageMagick / Python PIL 生成，**不依赖网络** AI 服务

### Out of scope
- 添加 LICENSE 文件本身（独立任务）
- 重写 architecture.md 等其它文档
- 截图：本仓库没有 polished UI screenshots，Screenshots 部分留**注释占位**而非空表格
- E2E captcha 真站测试

## Acceptance Criteria

- [ ] README.md 重写完成，结构对齐 Clippy
- [ ] docs/README.zh-CN.md 同步重写
- [ ] Banner 占位文件存在 docs/banner.png（即使是简易生成）
- [ ] 含完整 Credits 段（所有第三方依赖列名 + 链接）
- [ ] 含法律免责段（自动化伦理 + CFAA / TOS 类提醒）
- [ ] 含学习交流用途声明
- [ ] License 风险节（说明 Camoufox MPL、playwright-captcha Apache-2.0 拷贝来源等）
- [ ] 不再含 "Status: Alpha / MVP" 段（marketing 风要求）
- [ ] 不再含 Roadmap 段（移到 docs/ 内）
- [ ] CI / Release / Downloads / License 等 badges 顶部居中
- [ ] 工程命令仍可在文档其它地方查到（不丢失信息）

## Technical Notes

- Banner 生成方案：用 Python PIL 直接合成（深色画布 + 居中白色 logo + 标语文字）。脚本不入仓
- 法律免责文本参考：`examples/external/playwright-captcha/README.md` 的 "⚠️ LEGAL DISCLAIMER" 段
- Credits 引用源：
  - 前端：`package.json` dependencies
  - sidecar：`sidecar/requirements.txt` + `sidecar/captcha/cloudflare.py` 头部 attribution
  - Rust：`src-tauri/Cargo.toml` 主 crate
- Mimicry 标语候选（marketing 句）：
  - "A local-first desktop workspace for visual browser automation"
  - "Visual workflow editor + anti-detect browser, all on your machine"
  - "Build, record, and run browser workflows visually — with built-in anti-detection"