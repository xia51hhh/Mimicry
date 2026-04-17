## 变更摘要

- 

## 变更类型

- [ ] 功能
- [ ] 缺陷修复
- [ ] 文档
- [ ] CI/CD
- [ ] 发布相关

## 本地验证（请勾选）

- [ ] `pnpm install --frozen-lockfile`
- [ ] `pnpm typecheck`
- [ ] `python -m pytest tests/ -v`（在 `sidecar/`）
- [ ] `cargo clippy --all-targets --all-features -- -D warnings`（在 `src-tauri/`）
- [ ] `cargo test --all-targets --all-features`（在 `src-tauri/`）

## Release 检查（仅发布PR/提交时勾选）

- [ ] `CHANGELOG.md` 已新增并使用同名标题：`## vX.Y.Z`
- [ ] 三方版本一致：`package.json` / `src-tauri/Cargo.toml` / `src-tauri/tauri.conf.json`
- [ ] 将要推送的 tag 与版本一致（例如 `v0.1.0`）
- [ ] 若为预发布，tag 包含 `-rc` 后缀（例如 `v0.2.0-rc1`）

## 风险与回滚

- 风险点：
- 回滚方案：

## 关联信息

- 关联 Issue/任务：
- 备注：
