# Mimicry CI/CD & 自动更新指南

## 概述

当前已整合为**单一流水线**：` .github/workflows/pipeline.yml `。

| 流水线 | 文件 | 触发条件 | 用途 |
|--------|------|----------|------|
| Pipeline | `pipeline.yml` | `push` 到 `main` | 统一执行检查/测试；若满足发布条件则自动构建并发布 release |

## Pipeline 架构（方案 A）

```
push main
   │
   ▼
┌────────────┐
│  prepare   │  ← 校验三方版本一致性 + 检测当前commit是否被发布tag指向
└─────┬──────┘
      │
      ▼
┌────────────┐
│  quality   │  ← typecheck + sidecar pytest + rust clippy/test
└─────┬──────┘
      │
      ├─────────────── 无发布tag / 无绑定changelog
      │                 └─ 只输出检查结果并结束
      │
      └─────────────── 有发布tag 且 changelog绑定通过
                        ▼
                 ┌───────────────┐
                 │ build-sidecar │
                 └──────┬────────┘
                        ▼
                 ┌───────────────┐
                 │    release    │  ← tauri build + draft release
                 └──────┬────────┘
                        ▼
                 ┌───────────────┐
                 │ update-release│  ← 从CHANGELOG提取版本段落并发布
                 └───────────────┘
```

## 发布判定规则

Pipeline 会在 `prepare` 阶段进行以下判定：

1. `package.json`、`src-tauri/Cargo.toml`、`src-tauri/tauri.conf.json` 三方版本号必须一致
2. 当前 `push` 的 commit 必须被语义化 tag 指向（如 `v0.1.0`、`v0.2.0-rc1`）
3. `CHANGELOG.md` 必须存在同名标题：`## vX.Y.Z`

只有全部通过，才会进入 release 相关 job。

## 发布步骤（人工操作）

### 1) 更新 CHANGELOG

```markdown
## v0.x.x

### Added
- ...

### Fixed
- ...
```

> 标题必须与 tag 严格同名。

### 2) 同步版本号

确保以下三个文件一致：
- `package.json`
- `src-tauri/Cargo.toml`
- `src-tauri/tauri.conf.json`

### 3) 推送 main 与 tag

```bash
git add -A
git commit -m "release: v0.x.x"
git push origin main
git tag v0.x.x
git push origin v0.x.x
```

`-rc` 后缀会自动标记为 prerelease。

## 质量门槛（quality job）

- `pnpm install --frozen-lockfile`
- `pnpm typecheck`
- `python -m pytest tests/ -v`（`sidecar/`）
- `cargo clippy --all-targets --all-features -- -D warnings`（`src-tauri/`）
- `cargo test --all-targets --all-features`（`src-tauri/`）

## Node 20 迁移预防

为了避免 GitHub Actions Node 20 退役影响，pipeline 已设置：

```yaml
FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
```

并升级了关键 action 的主版本（`checkout` / `setup-node` / `setup-python`）。

## 自动更新

### 工作原理

1. 应用启动时通过 `@tauri-apps/plugin-updater` 请求 `latest.json`
2. 对比当前版本号与远程版本
3. 有新版本时弹出更新通知
4. 用户确认后下载并安装

### 更新支持矩阵

| 平台 | 格式 | 自动更新 |
|------|------|----------|
| Windows x64/ARM64 | NSIS | ✅ |
| Linux x64 | AppImage | ✅ |
| Linux x64 | deb | ❌ 引导到 Release |
| Linux ARM64/ARMv7 | deb/rpm | ❌ 引导到 Release |

### Endpoint

```
https://github.com/51hhh/Mimicry/releases/latest/download/latest.json
```

## 签名密钥

### 生成

```bash
pnpm tauri signer generate -w ~/.tauri/mimicry.key
```

### 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 值 |
|--------|-----|
| `TAURI_SIGNING_PRIVATE_KEY` | `~/.tauri/mimicry.key` 文件内容 |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | 密码（空密码则留空） |

公钥已配置在 `src-tauri/tauri.conf.json` → `plugins.updater.pubkey` 中。

### 密钥备份

- 私钥位置：`~/.tauri/mimicry.key`
- 公钥位置：`~/.tauri/mimicry.key.pub`
- **私钥丢失 = 所有已安装客户端无法自动更新**，务必安全备份

## 缓存策略

| 类型 | Action | 分组 |
|------|--------|------|
| Rust 编译 | Swatinem/rust-cache@v2 | OS + target |
| pnpm 依赖 | actions/cache@v4 | pnpm-lock.yaml hash |

## 本地开发

```bash
# 前端开发
pnpm dev

# Tauri 开发
pnpm tauri dev

# Sidecar 测试
cd sidecar && python -m pytest tests/ -v

# 完整构建
pnpm tauri build

# 代码检查
pnpm lint        # ESLint
pnpm format:check # Prettier
pnpm typecheck   # TypeScript
```
