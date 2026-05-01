# CI Pipeline 构建修复

## 背景
GitHub Actions Pipeline 在 commit `93aac98` (feat: Phase 3 跨Profile工作流执行) 首次运行时失败，Quality checks job 退出码 2。

## 根因分析

### 主要问题：e2e 测试在 CI 环境崩溃
- **文件**: `sidecar/tests/test_blocks_e2e.py`
- **原因**: 模块顶层直接执行 `BrowserController().launch(headless=False)`，pytest 收集测试时立即触发真实 Camoufox 浏览器启动
- **CI 环境**: ubuntu-24.04 无 X Server / 无 Display
- **错误信息**: `BrowserType.launch: Failed to launch the browser process. Looks like you launched a headed browser without having a XServer running.`
- **影响**: pytest collection interrupted (exit code 2)，整个测试套件中断

### 次要问题：Rust clippy lint 错误
- `src-tauri/src/commands/browser.rs:96` — `unnecessary_to_owned`: `&venv_dir.to_string_lossy().to_string()` 应为 `.as_ref()`
- `src-tauri/src/commands/profiles.rs:36` — `redundant_closure`: `.map_err(|e| AppError::Io(e))` 应为 `.map_err(AppError::Io)`

### 附加任务：密钥轮换
- 更新 updater 签名密钥对（用户重新生成）
- 更新 `tauri.conf.json` 中的 pubkey
- `key/` 目录添加到 `.gitignore`

## 修复方案

### 1. 重构 test_blocks_e2e.py
- **之前**: 模块级脚本，顶层 `ctrl = BrowserController(); ctrl.launch(headless=False)`
- **之后**: 正规 pytest 结构，使用 `@pytest.fixture(scope="module")` 延迟浏览器启动

### 2. 建立 pytest marker 体系
- 新建 `sidecar/tests/conftest.py`
- 注册 `e2e` marker
- CI 环境 (`CI=true`) 自动跳过 `e2e` 标记的测试
- `test_blocks_e2e.py` 和 `test_anti_detect.py` 统一使用 `pytestmark = pytest.mark.e2e`

### 3. Pipeline 更新
- pytest 命令: `python -m pytest tests/ -v -m "not e2e"`

### 4. Rust clippy 修复
- `browser.rs`: `venv_dir.to_string_lossy().as_ref()`
- `profiles.rs`: `.map_err(AppError::Io)`

### 5. 密钥与 gitignore
- `tauri.conf.json` pubkey 更新
- `.gitignore` 添加 `key/`

## 修改文件清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `sidecar/tests/test_blocks_e2e.py` | 重写 | 模块级脚本 → pytest fixture+class |
| `sidecar/tests/conftest.py` | 新建 | e2e marker 注册 + CI 自动跳过 |
| `sidecar/tests/test_anti_detect.py` | 修改 | skipif → e2e marker |
| `.github/workflows/pipeline.yml` | 修改 | `-m "not e2e"` |
| `src-tauri/src/commands/browser.rs` | 修改 | clippy fix |
| `src-tauri/src/commands/profiles.rs` | 修改 | clippy fix |
| `src-tauri/tauri.conf.json` | 修改 | updater pubkey |
| `.gitignore` | 修改 | 添加 key/ |

## 状态
- [x] 根因定位
- [x] 修复实施
- [x] 本地 clippy 验证通过
- [x] 推送到 GitHub
- [ ] CI 验证通过
