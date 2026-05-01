# techinz/playwright-captcha

## TL;DR

一个**专为 Playwright/Patchright/Camoufox 设计的 Captcha 求解库**，约 2.3k 行 Python，覆盖 4 种验证码类型（CF Turnstile、CF Interstitial、reCAPTCHA v2、v3）× 2 种求解模式（Click / API）。Mimicry 当前**完全没有验证码处理**，这个库是最直接的"补缺"——License 是 MIT，可作为可选 Block 集成。**首选 Click solver（不花钱、不用 API key），失败再降级到 2captcha API**。

## Repo Metadata

| | |
|---|---|
| URL | https://github.com/techinz/playwright-captcha |
| 最新 commit | `56b93e7` (2026-04-05)，本月 |
| 主语言 | Python |
| License | **MIT** (`pyproject.toml:11`，注意 LICENSE 文件文本是 Apache 2.0 开头但 pyproject 指定 MIT——**需澄清**) |
| 体量 | 核心 ~2.3k 行 + 示例脚本 + 测试 |
| 依赖 | `2captcha-python-async==1.5.1`（作者自己 fork）+ `aiofiles` + Playwright（外部依赖） |
| 维护活跃度 | 活跃 |
| 包名 | `playwright-captcha` (PyPI) |

⚠️ **License 矛盾点**：`pyproject.toml:11` 写 `license = "MIT"`，`LICENSE` 文件第一行是 `Apache License Version 2.0`。集成前需要 GH issue 澄清——MIT 和 Apache 2.0 都和 Mimicry 兼容，但事实上要明确。

## Positioning

面向已用 Playwright 系列的 Python 自动化作者：把"识别 captcha → 提取 sitekey → 提交求解 → 应用 token"流水线封装为可注册可扩展的 solver 体系。**Click solver 利用反检测浏览器（如 Camoufox）直接点过 CF Turnstile checkbox**——这是低成本路径。

## Tech Stack & Dependencies

| Layer | Tech |
|---|---|
| 入口 | `BaseSolver`（ABC） + `ClickSolver` + `TwoCaptchaSolver` |
| 注册器 | classmethod `register_detector` / `register_solver` / `register_applier`（每个 captcha 模块 `__init__.py` 自注册） |
| Captcha API 客户端 | 作者自己 fork 的 `2captcha-python-async`（因为上游不接受 PR）+ 内置 tencaptcha 客户端（127 行 async_api + 327 行 async_solver） |
| 浏览器 shim | `FrameworkType` 枚举（`PLAYWRIGHT` / `PATCHRIGHT` / `CAMOUFOX`），有 Camoufox-specific workaround |
| 测试 | pytest-asyncio + integration tests dir |

## Architecture

```
                    ┌──────────────────────┐
User code ────────► │  ClickSolver /       │ (BaseSolver subclass, async ctx mgr)
                    │  TwoCaptchaSolver    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌────────────────────────────────────────────┐
                    │  BaseSolver class registries (ClassVar):    │
                    │   _detectors  [CaptchaType] → detect fn     │
                    │   _solvers    [SolverType][CaptchaType]→fn  │
                    │   _appliers   [CaptchaType] → apply fn      │
                    └─────────────────┬──────────────────────────┘
                                      │
                                      ▼
                    captchas/cloudflare_turnstile/__init__.py
                       BaseSolver.register_solver(SolverType.click, ...,
                                                  solve_cloudflare_turnstile_click)
                       BaseSolver.register_solver(SolverType.twocaptcha, ...,
                                                  solve_cloudflare_turnstile_twocaptcha)
                       BaseSolver.register_detector(...)
                       BaseSolver.register_applier(...)
```

**注册表 + 装饰器**模式：每个 captcha 类型用独立子目录，`__init__.py` 把 detector/solver/applier 注册到 `BaseSolver` 的 ClassVar 字典里，实现"加新 captcha = 加一个文件夹"的可扩展性。

### 入口流程
1. `async with ClickSolver(framework=..., page=...) as solver:` → `solver.prepare()`（应用 framework patch）
2. 用户导航到目标页
3. `await solver.solve_captcha(captcha_container=page, captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE)`
4. `solver._solve_captcha_once`：detect → solve → apply
5. ctx 退出 → `cleanup()` 还原 patches

## Captcha Coverage Matrix

| Captcha 类型 | Click solver | API solver | Notes |
|---|---|---|---|
| Cloudflare Turnstile | ✅ | ✅ 2captcha | Click 在 Camoufox 下成功率最高 |
| Cloudflare Interstitial | ✅ | ✅ 2captcha | "Just a moment" 全屏挑战 |
| reCAPTCHA v2 | ❌ (无 click solver) | ✅ 2captcha + ✅ tencaptcha | 图形识别，必须打码服务 |
| reCAPTCHA v3 | ❌ | ✅ 2captcha + ✅ tencaptcha | 不可见 captcha，只能 API |
| hCaptcha / Cloudflare Managed Challenge | ❌ | ❌ | **未支持** |

## Key Code Patterns

### Pattern 1: ClassVar 注册表 + ABC

- 位置：`solvers/base_solver.py:15-88`
- 三组 ClassVar 字典：

  ```python
  _detectors: ClassVar[Dict[CaptchaType, Callable]] = {}
  _solvers:   ClassVar[Dict[SolverType, Dict[CaptchaType, Dict[str, Callable]]]] = {}
  _appliers:  ClassVar[Dict[CaptchaType, Callable]] = {}

  @classmethod
  def register_solver(cls, solver_type, captcha_type, solver_func, **kwargs): ...
  ```

- 加新 captcha 模块只需新建一个目录、写 `detect/solve/apply` 三个函数、在 `__init__.py` 里 `BaseSolver.register_*(...)`
- 对 Mimicry：完全适配 Mimicry Block 系统的扩展模式——可以做 `CaptchaBlock(captcha_type=..., solver=...)` Block，背后用同样的注册表

### Pattern 2: Cloudflare Turnstile Click Solver（核心算法）

- 位置：`solvers/click/cloudflare/solve_by_click.py:16-112`
- 流程：
  1. `detect_cloudflare_challenge` 检测页面是否含 CF challenge
  2. `search_shadow_root_iframes(src_filter='https://challenges.cloudflare.com/cdn-cgi/challenge-platform/')` —— **递归搜 shadow DOM 找 CF iframe**
  3. `get_ready_checkbox(iframes, attempts=10, delay=6s)` —— 等待 checkbox 准备好
  4. `click_checkbox(checkbox, attempts=3)` —— 重试 3 次点击
  5. Turnstile 等 `success` 元素出现；Interstitial 等 `networkidle` + 复检 challenge
- 关键见识：
  - Cloudflare 把 checkbox 放在 **shadow root 内的 iframe** 里——直接 `page.locator` 找不到，必须递归 shadow DOM
  - "click 不一定一次成功"——3 次 retry 是工程实践
  - 验证手段两路：**`success` 元素出现** 或 **`expected_content_selector` 出现**（用户传入）
- 对 Mimicry：直接借——加一个 `captcha.solve_cloudflare` action，参数 `(challenge_type, expected_content_selector)`，返回成功/失败

### Pattern 3: Detector → Solver → Applier 三段式

- 位置：每个 `captchas/*/{detect_data.py, apply.py, solvers/{click,twocaptcha}.py}`
- 解耦：
  - **Detector**：从 DOM 提取 sitekey + action（`detect_turnstile_data` 在 `cloudflare_turnstile/detect_data.py:11-34`）
  - **Solver**：调用打码 API 或 click 拿 token
  - **Applier**：把 token 应用到页面（`apply.py:11-50` 通过 `page.evaluate` 调用 `applyCloudflareTurnstile.js` 模板）
- 这种解耦让"换打码服务"只动 Solver，"网站升级了 captcha 嵌入方式"只动 Applier
- 对 Mimicry：值得借——把"提取 sitekey/sitedata"作为可独立调用的 sub-action，便于上层 workflow 灵活组合

### Pattern 4: Camoufox `add_init_script` workaround

- 位置：`captchas/cloudflare_turnstile/apply.py:24-48`，作者还有独立 repo `camoufox-add_init_script`
- 问题：Camoufox 的 Juggler 协议沙箱让 Playwright 的 `add_init_script` 无法把变量注入到 main world，captcha applier 需要这个能力
- workaround：用一个 Firefox addon 把 init script 路径桥接到 main world
- `getattr(page.add_init_script, 'is_camoufox_workaround', None) is True` 检测是否是 patched 版本
- 对 Mimicry：Mimicry 也用 Camoufox。**这个 workaround 本身就是 Mimicry 应该关心的——Mimicry 当前 RecordingEngine / `_init_scripts` 路径是否遇到了同样的 main world 问题？需交叉检查 sidecar/browser/recorder.py**

## Public API Examples

### Click solver（Turnstile）

```python
async with ClickSolver(framework=FrameworkType.PLAYWRIGHT, page=page) as solver:
    await page.goto('https://2captcha.com/demo/cloudflare-turnstile')
    await asyncio.sleep(5)
    container = page.locator('#cf-turnstile')
    await container.wait_for()
    await solver.solve_captcha(
        captcha_container=page,
        captcha_type=CaptchaType.CLOUDFLARE_TURNSTILE
    )
```

### 2captcha API solver（reCAPTCHA v2）

```python
from twocaptcha import AsyncTwoCaptcha
client = AsyncTwoCaptcha(API_KEY)
async with TwoCaptchaSolver(framework=..., page=page, async_two_captcha_client=client) as solver:
    await solver.solve_captcha(captcha_type=CaptchaType.RECAPTCHA_V2)
```

### Camoufox 集成（特殊 setup）

需要 `i_know_what_im_doing=True`、`config={'forceScopeAccess': True}`、`disable_coop=True`、`main_world_eval=True`、`addons=[get_addon_path()]` —— **5 个非默认参数**才能让 Camoufox 跑这个库。这是 Mimicry 集成的工程负担。

## Engineering Practices

### 仓库结构（清晰，目录即抽象层）
- `solvers/{base, click, api/{twocaptcha, tencaptcha}}` —— 求解模式
- `captchas/{cloudflare_turnstile, cloudflare_interstitial, recaptcha_v2, recaptcha_v3}/` —— 每种 captcha 自含 detect/apply/solvers
- `examples/{cloudflare, recaptcha}/` —— 完整可跑示例
- `utils/{exceptions, dom_helpers, regex_helpers, validators, js_script, js_scripts/, camoufox_add_init_script/}`

### 测试
- pytest + pytest-asyncio + pytest-cov
- `tests/integration/` 含 integration 测试
- 但**真测 captcha 必须连 2captcha API + 烧 captcha 余额**——要么 mock，要么手动跑——这是 captcha 库共同的工程难题

### CI
- 看到 `.github/workflows/` 目录但本次未读取具体文件
- 测试基础在，但能否在 CI 跑实战 captcha 是另一回事

### 文档
- 320 行 README + 完整示例脚本
- 工具自带 logger 用 `logging.getLogger(__name__)`，集成时方便接管

### 错误处理
- `CaptchaSolvingError` / `CaptchaDetectionError` / `CaptchaApplyingError` typed exceptions（`utils/exceptions.py`）
- max_attempts + attempt_delay 内建重试

### 发布
- pip / pypi
- 无 Docker 镜像

## Gaps vs. Mimicry

Mimicry 当前**完全没有 captcha 处理**。这个库就是缺失的那块。

| 维度 | playwright-captcha | Mimicry |
|---|---|---|
| Captcha 检测 | 4 类自动 | 无 |
| Click solver | CF Turnstile/Interstitial | 无 |
| API solver | 2captcha / tencaptcha 双家 | 无 |
| Token applier | `page.evaluate` 注入 callback | 无 |
| Shadow DOM 递归 | 实现了 | 无 |
| Captcha 类型枚举 | `CaptchaType` enum | 无 |
| Framework abstraction | `FrameworkType` 区分 PW/Patchright/Camoufox | 没必要（Mimicry 锁定 Camoufox） |
| License | MIT (pyproject) / Apache (LICENSE) ⚠️ | Mimicry 无 LICENSE |

## Borrow List

| # | 借鉴点 | Mimicry 目标模块 | 优先级 | 成本/风险 |
|---|---|---|---|---|
| 1 | 集成为可选 Captcha Block | sidecar 新增 `sidecar/captcha/`，封装为 `captcha.solve` action（参数 `type` + `solver_mode`），workflow 中作为 Block 节点 | **S** | 低-中，~3 天；前置依赖：解决 license 矛盾、解决 Camoufox add_init_script workaround |
| 2 | Detector / Solver / Applier 三段解耦设计 | sidecar 内部架构 | **S** | 低，纯设计参考 |
| 3 | ClassVar 注册表模式（`register_*`） | `sidecar/engine/action_map.py` 风格扩展 | M | 低，但要决定是否替代当前 `@rpc_method` 装饰器 |
| 4 | Shadow root 递归搜索工具 | `sidecar/utils/dom.py` 增加 utility | S | 低，独立工具 |
| 5 | typed exceptions（CaptchaSolvingError 等） | sidecar 错误模型 | S | 低 |
| 6 | Camoufox `add_init_script` workaround | 交叉检查 Mimicry RecordingEngine 是否也踩到了，必要时引入相同 addon | **S** | 低，关键是检查 |
| 7 | 把 license 矛盾提 GH issue 让作者澄清 | (外部沟通) | S | 0 成本 |
| 8 | "首选 Click solver、失败降级 API solver"的 fallback 策略 | Mimicry 的 Block onError 策略可固化为 captcha-specific preset | M | 中，但很有价值 |

## Do NOT Borrow

- **`tencaptcha` 内置子模块**（共 ~570 行）—— Mimicry 不需要绑定特定打码服务，应让用户传入自己的 client
- **作者 fork 的 `2captcha-python-async`** —— 不要让 Mimicry 依赖一个非主流 fork，应等上游接 PR 或自己写薄客户端
- **`FrameworkType` 抽象** —— Mimicry 锁定 Camoufox，多 framework shim 是浪费
- **直接把整个 lib pip 安装进 sidecar** —— 它带 2captcha 客户端等 Mimicry 不需要的部分；建议**抽取核心算法（click solver + detector/applier）到 Mimicry 自己的 captcha 模块**，license 兼容直接拷贝代码

## Open Questions

- **License 真相**：`pyproject.toml` 说 MIT，`LICENSE` 文件是 Apache 2.0。哪个为准？需要交叉检查 PyPI 元数据 + 提 issue
- **Camoufox add_init_script workaround**：Mimicry 自己的 `BrowserController` 用 `add_init_script` 做录制器注入，**是否也存在 main world 不可达问题**？需要在 sidecar 跑实测
- **测试策略**：怎么在 CI 测真实 captcha？这个库似乎也没解决——Mimicry 集成时同样问题
- **hCaptcha / Cloudflare Managed Challenge 不支持**：Mimicry 走 Block 路线时这是已知缺口；可以加一个"未实现，请人工处理"的明确错误而不是无声失败
- **更新频率**：上游一次升级会跟得上吗？建议把 click solver 拷贝代码内置而不是 pip 强依赖
