# Phase 1: 稳固基础 — 从"能跑"到"可靠"

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复运行时 bug、实现指纹/Profile 持久化、重构条件评估器支持组合逻辑、RPC 超时分级、action-map 单源生成

**Architecture:** 
- 指纹持久化：利用 Camoufox 原生 `persistent_context` + `user_data_dir` + BrowserForge 指纹序列化到 SQLite
- 条件评估器：递归下降解析器替换正则匹配链，支持 `and`/`or`/`not` + 比较运算符
- RPC 超时：Rust 侧按方法分级超时，Python 侧无需改动
- Action-map：JSON schema 单源 → 双端代码生成脚本

**Tech Stack:** Python 3.11+, Camoufox (Playwright), Rust/Tauri, TypeScript, BrowserForge

---

## 文件结构

### 新建文件
- `sidecar/engine/condition_parser.py` — 递归下降条件解析器
- `sidecar/tests/test_condition_parser.py` — 条件解析器测试
- `scripts/sync-action-map.py` — action-map 单源生成脚本
- `shared/action-map.json` — action-map 单一源定义

### 修改文件
- `sidecar/browser/controller.py` — 修复 handle_download、添加 persistent_context 支持
- `sidecar/engine/executor.py` — 接入新条件解析器
- `src-tauri/src/ipc/sidecar.rs` — RPC 超时分级
- `sidecar/engine/action_map.py` — 改为从 JSON 生成（或验证一致性）
- `src/types/action-map.ts` — 同上
- `src-tauri/src/db/mod.rs` — 添加 profiles 表（指纹+user_data_dir 持久化）

---

## Task 1: 修复 handle_download bug

**Files:**
- Modify: `sidecar/browser/controller.py:277-283`
- Test: `sidecar/tests/test_executor.py`

**问题分析：**
`handle_download` 的 `with expect_download` 块内是 `pass`。`expect_download` 是一个 context manager，需要在 `with` 块内执行**触发下载的操作**。当前实现中 `pass` 意味着没有任何操作会触发下载，`expect_download` 会在超时后抛出 TimeoutError。

正确的设计应该是：`handle_download` 不应该自己触发下载（它不知道哪个操作触发），而应该作为"下一个操作的包装器"使用。但在当前 block 架构中，每个 action 是独立节点。

**解决方案：** 改为事后捕获模式 — 监听 download 事件，在超时内等待下载完成。

- [ ] **Step 1: 写失败测试**

在 `sidecar/tests/test_executor.py` 中添加：

```python
def test_handle_download_calls_controller(self):
    """handle_download should call controller.handle_download with correct args."""
    self.ctrl.handle_download = MagicMock(return_value="/tmp/file.pdf")
    node = {"action": "handle_download", "savePath": "/tmp/file.pdf", "timeout": 5000}
    self.executor._execute_action(node, self.ctrl, self.ctx)
    self.ctrl.handle_download.assert_called_once_with("/tmp/file.pdf", timeout=5000)
    assert self.ctx.get_var("$_result") == "/tmp/file.pdf"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd sidecar && python -m pytest tests/test_executor.py::TestBasicActions::test_handle_download_calls_controller -v
```

- [ ] **Step 3: 修复 controller.handle_download 实现**

将 `sidecar/browser/controller.py` 中 handle_download 改为事件监听模式：

```python
def handle_download(self, save_path: str, timeout: int = 30000) -> str:
    """Wait for an ongoing or upcoming download and save it."""
    with self._page.expect_download(timeout=timeout) as download_info:
        # Download is triggered by a preceding action (click etc.)
        # We just wait for it. If no download starts within timeout, it throws.
        self._page.wait_for_timeout(min(timeout, 500))
    download = download_info.value
    download.save_as(save_path)
    return save_path
```

注意：这仍然有架构问题（download 需要在 with 块内被触发）。更可靠的方案是用 `page.on("download")` 事件监听：

```python
def handle_download(self, save_path: str, timeout: int = 30000) -> str:
    """Wait for a download event and save the file."""
    import threading
    download_holder = [None]
    event = threading.Event()
    
    def on_download(download):
        download_holder[0] = download
        event.set()
    
    self._page.on("download", on_download)
    try:
        if not event.wait(timeout=timeout / 1000):
            raise TimeoutError(f"No download within {timeout}ms")
        download = download_holder[0]
        download.save_as(save_path)
        return save_path
    finally:
        self._page.remove_listener("download", on_download)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_executor.py -v -k "download"
```

- [ ] **Step 5: Commit**

```bash
git add sidecar/browser/controller.py sidecar/tests/test_executor.py
git commit -m "fix: handle_download 改为事件监听模式，修复空 with 块 bug"
```

---

## Task 2: 条件评估器重构 — 递归下降解析器

**Files:**
- Create: `sidecar/engine/condition_parser.py`
- Create: `sidecar/tests/test_condition_parser.py`
- Modify: `sidecar/engine/executor.py:394-447`

**设计：** 替换 8 个 `re.match` 硬编码模式为递归下降解析器，支持：
- 逻辑组合：`and`, `or`, `not`
- 比较运算符：`==`, `!=`, `>`, `<`, `>=`, `<=`
- 函数调用：`exists()`, `visible()`, `equals()`, `contains()`, `regex()`, `url_contains()`, `text()`
- 变量引用：`$var`
- 括号分组：`(expr and expr) or expr`

### Step 2.1: 写解析器测试

- [ ] **Step 1: 创建 test_condition_parser.py**

```python
"""Tests for the condition parser."""
import pytest
from unittest.mock import MagicMock
from engine.condition_parser import evaluate_condition


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.get_element_count.return_value = 1
    ctrl.is_visible.return_value = True
    ctrl.get_url.return_value = "https://example.com/dashboard"
    ctrl.get_element_text.return_value = "Hello"
    return ctrl


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.get_var.side_effect = lambda name, default=None: {
        "$count": 5,
        "$name": "alice",
        "$empty": "",
    }.get(name, default)
    ctx.resolve.side_effect = lambda s: s  # passthrough
    return ctx


class TestSimpleConditions:
    def test_exists(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('exists("#btn")', mock_ctrl, mock_ctx) is True
        mock_ctrl.get_element_count.assert_called_with("#btn")

    def test_exists_false(self, mock_ctrl, mock_ctx):
        mock_ctrl.get_element_count.return_value = 0
        assert evaluate_condition('exists("#btn")', mock_ctrl, mock_ctx) is False

    def test_visible(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('visible(".modal")', mock_ctrl, mock_ctx) is True

    def test_equals(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('equals("hello", "hello")', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('equals("hello", "world")', mock_ctrl, mock_ctx) is False

    def test_contains(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('contains("hello world", "world")', mock_ctrl, mock_ctx) is True

    def test_regex(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('regex("abc123", "\\d+")', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('regex("abc", "\\d+")', mock_ctrl, mock_ctx) is False

    def test_url_contains(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('url_contains("dashboard")', mock_ctrl, mock_ctx) is True

    def test_text_equals(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('text("#heading") == "Hello"', mock_ctrl, mock_ctx) is True

    def test_variable_equals_string(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$name == "alice"', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$name == "bob"', mock_ctrl, mock_ctx) is False

    def test_variable_equals_number(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count == 5', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count == 3', mock_ctrl, mock_ctx) is False


class TestComparisonOperators:
    def test_not_equals(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count != 3', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count != 5', mock_ctrl, mock_ctx) is False

    def test_greater_than(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count > 3', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count > 5', mock_ctrl, mock_ctx) is False

    def test_less_than(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count < 10', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count < 5', mock_ctrl, mock_ctx) is False

    def test_greater_equal(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count >= 5', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count >= 6', mock_ctrl, mock_ctx) is False

    def test_less_equal(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('$count <= 5', mock_ctrl, mock_ctx) is True
        assert evaluate_condition('$count <= 4', mock_ctrl, mock_ctx) is False


class TestLogicalOperators:
    def test_not(self, mock_ctrl, mock_ctx):
        mock_ctrl.get_element_count.return_value = 0
        assert evaluate_condition('not exists("#btn")', mock_ctrl, mock_ctx) is True

    def test_and(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('exists("#btn") and visible(".modal")', mock_ctrl, mock_ctx) is True
        mock_ctrl.get_element_count.return_value = 0
        assert evaluate_condition('exists("#btn") and visible(".modal")', mock_ctrl, mock_ctx) is False

    def test_or(self, mock_ctrl, mock_ctx):
        mock_ctrl.get_element_count.return_value = 0
        assert evaluate_condition('exists("#btn") or visible(".modal")', mock_ctrl, mock_ctx) is True
        mock_ctrl.is_visible.return_value = False
        assert evaluate_condition('exists("#btn") or visible(".modal")', mock_ctrl, mock_ctx) is False

    def test_complex_combination(self, mock_ctrl, mock_ctx):
        assert evaluate_condition(
            'exists("#btn") and (visible(".modal") or $count > 3)',
            mock_ctrl, mock_ctx
        ) is True

    def test_not_with_and(self, mock_ctrl, mock_ctx):
        mock_ctrl.get_element_count.return_value = 0
        assert evaluate_condition(
            'not exists("#btn") and visible(".modal")',
            mock_ctrl, mock_ctx
        ) is True


class TestEdgeCases:
    def test_empty_condition(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('', mock_ctrl, mock_ctx) is False

    def test_whitespace_handling(self, mock_ctrl, mock_ctx):
        assert evaluate_condition('  exists( "#btn" )  ', mock_ctrl, mock_ctx) is True

    def test_variable_resolve_in_args(self, mock_ctrl, mock_ctx):
        """Variables in function arguments should be resolved."""
        ctx = mock_ctx
        ctx.resolve.side_effect = lambda s: s.replace("$name", "alice")
        assert evaluate_condition('equals("$name", "alice")', mock_ctrl, ctx) is True

    def test_exception_in_exists_returns_false(self, mock_ctrl, mock_ctx):
        mock_ctrl.get_element_count.side_effect = Exception("timeout")
        assert evaluate_condition('exists("#btn")', mock_ctrl, mock_ctx) is False
```

- [ ] **Step 2: 运行测试验证全部失败**

```bash
cd sidecar && python -m pytest tests/test_condition_parser.py -v
```
Expected: ImportError — `engine.condition_parser` 不存在

- [ ] **Step 3: 实现 condition_parser.py**

```python
"""Recursive descent condition parser for workflow conditions.

Grammar:
    expr       -> or_expr
    or_expr    -> and_expr ('or' and_expr)*
    and_expr   -> not_expr ('and' not_expr)*
    not_expr   -> 'not' not_expr | comparison
    comparison -> value (('==' | '!=' | '>' | '<' | '>=' | '<=') value)?
    value      -> function_call | variable | string | number | '(' expr ')'
    function_call -> IDENT '(' args ')'
    args       -> string (',' string)*
    variable   -> '$' IDENT
    string     -> '"' ... '"'
    number     -> DIGIT+
"""
from __future__ import annotations
import re
from typing import Any
from loguru import logger


class _Token:
    __slots__ = ("type", "value")
    def __init__(self, type: str, value: str):
        self.type = type
        self.value = value
    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"


_TOKEN_RE = re.compile(r"""
    \s*(?:
        (and|or|not)\b        |  # keywords
        (==|!=|>=|<=|>|<)     |  # operators
        (\$\w+)               |  # variables
        ([a-zA-Z_]\w*)        |  # identifiers (function names)
        "([^"\\]*(?:\\.[^"\\]*)*)" |  # double-quoted strings
        '([^'\\]*(?:\\.[^'\\]*)*)'  |  # single-quoted strings
        (\d+(?:\.\d+)?)       |  # numbers
        ([(),])                  # punctuation
    )\s*
""", re.VERBOSE)


def _tokenize(condition: str) -> list[_Token]:
    tokens = []
    pos = 0
    for m in _TOKEN_RE.finditer(condition):
        kw, op, var, ident, dstr, sstr, num, punc = m.groups()
        if kw:
            tokens.append(_Token("KW", kw))
        elif op:
            tokens.append(_Token("OP", op))
        elif var:
            tokens.append(_Token("VAR", var))
        elif ident:
            tokens.append(_Token("IDENT", ident))
        elif dstr is not None:
            tokens.append(_Token("STR", dstr.replace('\\"', '"')))
        elif sstr is not None:
            tokens.append(_Token("STR", sstr.replace("\\'", "'")))
        elif num:
            tokens.append(_Token("NUM", num))
        elif punc:
            tokens.append(_Token("PUNC", punc))
        pos = m.end()
    tokens.append(_Token("EOF", ""))
    return tokens


class _Parser:
    def __init__(self, tokens: list[_Token], ctrl, ctx):
        self.tokens = tokens
        self.pos = 0
        self.ctrl = ctrl
        self.ctx = ctx

    def peek(self) -> _Token:
        return self.tokens[self.pos]

    def advance(self) -> _Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type: str, value: str | None = None) -> _Token:
        tok = self.advance()
        if tok.type != type or (value is not None and tok.value != value):
            raise ValueError(f"Expected {type}({value}), got {tok}")
        return tok

    def parse(self) -> bool:
        result = self._or_expr()
        return bool(result)

    def _or_expr(self):
        left = self._and_expr()
        while self.peek().type == "KW" and self.peek().value == "or":
            self.advance()
            right = self._and_expr()
            left = left or right
        return left

    def _and_expr(self):
        left = self._not_expr()
        while self.peek().type == "KW" and self.peek().value == "and":
            self.advance()
            right = self._not_expr()
            left = left and right
        return left

    def _not_expr(self):
        if self.peek().type == "KW" and self.peek().value == "not":
            self.advance()
            return not self._not_expr()
        return self._comparison()

    def _comparison(self):
        left = self._value()
        if self.peek().type == "OP":
            op = self.advance().value
            right = self._value()
            return self._compare(left, op, right)
        return left

    def _compare(self, left, op: str, right):
        # Try numeric comparison
        try:
            l, r = float(left), float(right)
            match op:
                case "==": return l == r
                case "!=": return l != r
                case ">":  return l > r
                case "<":  return l < r
                case ">=": return l >= r
                case "<=": return l <= r
        except (ValueError, TypeError):
            pass
        # String comparison
        l_str, r_str = str(left), str(right)
        match op:
            case "==": return l_str == r_str
            case "!=": return l_str != r_str
            case ">":  return l_str > r_str
            case "<":  return l_str < r_str
            case ">=": return l_str >= r_str
            case "<=": return l_str <= r_str
        return False

    def _value(self):
        tok = self.peek()

        if tok.type == "PUNC" and tok.value == "(":
            self.advance()
            result = self._or_expr()
            self.expect("PUNC", ")")
            return result

        if tok.type == "IDENT":
            return self._function_call()

        if tok.type == "VAR":
            self.advance()
            return self.ctx.get_var(tok.value, "")

        if tok.type == "STR":
            self.advance()
            return self.ctx.resolve(tok.value)

        if tok.type == "NUM":
            self.advance()
            return float(tok.value) if "." in tok.value else int(tok.value)

        # Fallback for EOF or unexpected
        return False

    def _function_call(self) -> Any:
        name_tok = self.advance()
        name = name_tok.value
        self.expect("PUNC", "(")
        args = []
        while self.peek().type != "PUNC" or self.peek().value != ")":
            if args:
                self.expect("PUNC", ",")
            tok = self.advance()
            if tok.type == "STR":
                args.append(self.ctx.resolve(tok.value))
            elif tok.type == "VAR":
                args.append(str(self.ctx.get_var(tok.value, "")))
            elif tok.type == "NUM":
                args.append(float(tok.value) if "." in tok.value else int(tok.value))
            else:
                args.append(tok.value)
        self.expect("PUNC", ")")

        return self._eval_function(name, args)

    def _eval_function(self, name: str, args: list) -> Any:
        ctrl = self.ctrl
        try:
            match name:
                case "exists":
                    return ctrl.get_element_count(args[0]) > 0
                case "visible":
                    return ctrl.is_visible(args[0])
                case "equals":
                    return str(args[0]) == str(args[1])
                case "contains":
                    return str(args[1]) in str(args[0])
                case "regex":
                    return bool(re.search(str(args[1]), str(args[0])))
                case "url_contains":
                    return str(args[0]) in ctrl.get_url()
                case "text":
                    return ctrl.get_element_text(args[0])
                case _:
                    logger.warning(f"Unknown function: {name}")
                    return False
        except Exception as e:
            logger.debug(f"Condition function {name} failed: {e}")
            return False


def evaluate_condition(condition: str, ctrl, ctx) -> bool:
    """Evaluate a condition string and return True/False."""
    condition = condition.strip()
    if not condition:
        return False
    try:
        tokens = _tokenize(condition)
        parser = _Parser(tokens, ctrl, ctx)
        return parser.parse()
    except Exception as e:
        logger.warning(f"Failed to evaluate condition '{condition}': {e}")
        return False
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd sidecar && python -m pytest tests/test_condition_parser.py -v
```
Expected: ALL PASS

- [ ] **Step 5: 接入 executor.py**

替换 `executor.py` 中 `_evaluate_condition` 方法：

```python
def _evaluate_condition(self, condition: str, ctrl, ctx) -> bool:
    from engine.condition_parser import evaluate_condition
    return evaluate_condition(condition, ctrl, ctx)
```

- [ ] **Step 6: 运行全量测试**

```bash
cd sidecar && python -m pytest tests/test_executor.py tests/test_condition_parser.py -v
```
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add sidecar/engine/condition_parser.py sidecar/tests/test_condition_parser.py sidecar/engine/executor.py
git commit -m "feat: 条件评估器重构为递归下降解析器，支持 and/or/not + 比较运算符"
```

---

## Task 3: 指纹 + Profile 持久化

**Files:**
- Modify: `sidecar/browser/controller.py:60-92` — launch() 添加 persistent_context 支持
- Modify: `src-tauri/src/db/mod.rs` — 添加 profiles 表
- Modify: `sidecar/rpc/methods.py` 或对应 rpc_methods — 添加 profile CRUD RPC
- Create: `sidecar/browser/profile.py` — 指纹序列化/反序列化

**设计决策：**
- Camoufox 原生支持 `persistent_context=True` + `user_data_dir`
- BrowserForge 指纹对象可 JSON 序列化
- Profile = `{id, name, fingerprint_json, user_data_dir, proxy, created_at}`
- 用户可选"创建新 Profile"或"复用已有 Profile"启动浏览器
- 默认行为不变（随机指纹 + 临时 context），指纹持久化是可选功能

### Step 3.1: Profile 管理模块

- [ ] **Step 1: 创建 profile.py**

```python
"""Browser profile management — fingerprint persistence and user data dirs."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from loguru import logger


@dataclass
class BrowserProfile:
    """A persistent browser profile with fingerprint and user data."""
    id: str
    name: str
    fingerprint: dict[str, Any] = field(default_factory=dict)
    user_data_dir: str = ""
    proxy: dict | None = None
    os_target: str = "windows"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BrowserProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def generate_fingerprint(os_target: str = "windows") -> dict:
    """Generate a new BrowserForge fingerprint and return as serializable dict."""
    try:
        from browserforge.fingerprints import FingerprintGenerator
        fg = FingerprintGenerator(browser="firefox")
        fp = fg.generate(os=os_target)
        # BrowserForge Fingerprint objects have a to_dict or similar
        return json.loads(json.dumps(fp.__dict__, default=str))
    except Exception as e:
        logger.warning(f"Failed to generate fingerprint: {e}")
        return {}


def get_profiles_dir() -> Path:
    """Get the base directory for storing browser profiles."""
    base = Path(os.environ.get("MIMICRY_DATA_DIR", Path.home() / ".mimicry"))
    profiles_dir = base / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir


def get_profile_data_dir(profile_id: str) -> str:
    """Get the user_data_dir path for a given profile."""
    p = get_profiles_dir() / profile_id
    p.mkdir(parents=True, exist_ok=True)
    return str(p)
```

- [ ] **Step 2: 修改 controller.py launch() 支持 profile**

在 `launch()` 方法签名中添加 `profile: BrowserProfile | None = None` 参数：

```python
def launch(self, headless: bool = False, proxy: dict | None = None, 
           profile: dict | None = None):
    if self._browser:
        logger.warning("Browser already running")
        return

    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        raise RuntimeError("Camoufox is not installed. Run camoufox.install first.")

    kwargs = {
        "headless": headless,
        "humanize": True,
        "os": "windows",
        "geoip": True,
        "block_webrtc": True,
        "enable_cache": True,
        "disable_coop": True,
        "i_know_what_im_doing": True,
    }
    if proxy:
        kwargs["proxy"] = proxy

    # Apply profile (persistent context + fingerprint)
    if profile:
        if profile.get("fingerprint"):
            try:
                from browserforge.fingerprints import FingerprintGenerator
                fg = FingerprintGenerator(browser="firefox")
                fp = fg.generate(os=profile.get("os_target", "windows"))
                # Use stored fingerprint config
                kwargs["config"] = profile["fingerprint"]
            except Exception as e:
                logger.warning(f"Failed to apply fingerprint: {e}")
        
        user_data_dir = profile.get("user_data_dir", "")
        if user_data_dir:
            kwargs["persistent_context"] = True
            kwargs["user_data_dir"] = user_data_dir

        if profile.get("proxy"):
            kwargs["proxy"] = profile["proxy"]
        if profile.get("os_target"):
            kwargs["os"] = profile["os_target"]

    # Fit browser window to screen
    try:
        w, h = self._get_screen_size()
        kwargs["window"] = (max(w - 100, 800), max(h - 150, 600))
    except Exception:
        pass

    logger.info(f"Launching Camoufox (headless={headless}, profile={bool(profile)})")
    self._camoufox = Camoufox(**kwargs)
    self._browser = self._camoufox.__enter__()
    
    # persistent_context returns context directly, not browser
    if profile and profile.get("user_data_dir"):
        # In persistent context mode, Camoufox returns a BrowserContext
        self._page = self._browser.pages[0] if self._browser.pages else self._browser.new_page()
    else:
        self._page = self._browser.new_page()
    
    logger.info("Browser launched")
```

- [ ] **Step 3: 添加 RPC 方法支持 profile 参数**

在浏览器启动的 RPC 方法中传递 profile：

在 `sidecar/browser/actions.py` 的 `browser_launch` RPC 方法中添加 profile 参数支持。

- [ ] **Step 4: 运行现有测试确保不破坏**

```bash
cd sidecar && python -m pytest tests/ --ignore=tests/test_blocks_e2e.py --ignore=tests/test_anti_detect.py -v
```
Expected: ALL PASS（profile=None 时行为不变）

- [ ] **Step 5: Commit**

```bash
git add sidecar/browser/profile.py sidecar/browser/controller.py sidecar/browser/actions.py
git commit -m "feat: 指纹+Profile 持久化支持 (Camoufox persistent_context)"
```

---

## Task 4: RPC 超时分级

**Files:**
- Modify: `src-tauri/src/ipc/sidecar.rs` — 按方法名分级超时

**当前状态：** 所有 RPC 调用统一 600 秒超时。

**目标：**
- `ping` / `echo` / `system.info`: 5 秒
- 浏览器操作（`browser.*`）: 60 秒
- `workflow.execute`: 不等待（异步方法，Python 侧已在后台线程执行）
- 其他: 30 秒

- [ ] **Step 1: 在 sidecar.rs 中添加超时分级函数**

```rust
fn rpc_timeout(method: &str) -> std::time::Duration {
    match method {
        "ping" | "echo" | "system.info" => std::time::Duration::from_secs(5),
        m if m.starts_with("browser.") => std::time::Duration::from_secs(60),
        "workflow.execute" => std::time::Duration::from_secs(600),
        _ => std::time::Duration::from_secs(30),
    }
}
```

- [ ] **Step 2: 替换硬编码超时**

将 `let timeout_dur = std::time::Duration::from_secs(600);` 替换为 `let timeout_dur = rpc_timeout(&method);`

- [ ] **Step 3: Cargo check**

```bash
cd src-tauri && cargo check
```
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/ipc/sidecar.rs
git commit -m "feat: RPC 超时按方法分级 (5s/30s/60s/600s)"
```

---

## Task 5: Action-Map 单源生成

**Files:**
- Create: `shared/action-map.json` — 单一源定义
- Create: `scripts/sync-action-map.py` — 验证/生成脚本
- Modify: `sidecar/engine/action_map.py` — 从 JSON 加载或验证
- Modify: `src/types/action-map.ts` — 注释标记为自动生成

**设计：** 考虑到双端代码生成的维护成本，采用更轻量的方案 — 单源 JSON + CI 验证脚本。手动修改仍在 action_map.py 和 action-map.ts 中进行，但 CI/本地脚本会检测不一致。

- [ ] **Step 1: 创建 shared/action-map.json**

从现有 action_map.py 提取所有映射对，生成 JSON：

```json
{
  "$schema": "action-map-schema",
  "description": "Single source of truth for frontend↔backend action name mapping",
  "mappings": {
    "Navigate": "open",
    "GoBack": "back",
    "GoForward": "forward",
    "Reload": "reload",
    "Click": "click",
    "DoubleClick": "dblclick",
    "Type": "type",
    "Clear": "clear",
    "SelectOption": "select",
    "Hover": "hover",
    "Scroll": "scroll",
    "Focus": "focus",
    "PressKey": "press_key",
    "WaitForElement": "wait",
    "ExtractText": "extract_text",
    "ExtractAttribute": "extract_attr",
    "ExtractTable": "extract_table",
    "GetUrl": "get_url",
    "SetVariable": "set",
    "Screenshot": "screenshot",
    "Log": "log",
    "Sleep": "sleep",
    "Fail": "fail",
    "NewTab": "new_tab",
    "SwitchTab": "switch_tab",
    "CloseTab": "close_tab",
    "HandleDialog": "handle_dialog",
    "UploadFile": "upload_file",
    "RunScript": "run_script",
    "HttpRequest": "http_request",
    "Export": "export",
    "Comment": "comment",
    "SwitchFrame": "switch_frame",
    "WaitForPage": "wait_for_page",
    "Cookie": "cookie",
    "ElementExists": "element_exists",
    "HandleDownload": "handle_download",
    "Transform": "transform",
    "ExecuteWorkflow": "execute_workflow",
    "LoopElements": "loop_elements",
    "Stop": "stop",
    "LoopBreakpoint": "loop_breakpoint",
    "WaitConnections": "wait_connections"
  }
}
```

- [ ] **Step 2: 创建验证脚本 scripts/sync-action-map.py**

```python
#!/usr/bin/env python3
"""Verify that action-map.json, action_map.py, and action-map.ts are in sync."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

def load_json_source():
    with open(ROOT / "shared" / "action-map.json") as f:
        return json.load(f)["mappings"]

def load_python_map():
    text = (ROOT / "sidecar" / "engine" / "action_map.py").read_text()
    # Extract the dict literal from _FRONTEND_TO_BACKEND = { ... }
    m = re.search(r'_FRONTEND_TO_BACKEND\s*=\s*\{([^}]+)\}', text, re.DOTALL)
    if not m:
        sys.exit("Cannot parse action_map.py")
    pairs = re.findall(r'"(\w+)":\s*"(\w+)"', m.group(1))
    return dict(pairs)

def load_ts_map():
    text = (ROOT / "src" / "types" / "action-map.ts").read_text()
    m = re.search(r'frontendToBackend.*?=\s*\{([^}]+)\}', text, re.DOTALL)
    if not m:
        sys.exit("Cannot parse action-map.ts")
    pairs = re.findall(r"['\"](\w+)['\"]:\s*['\"](\w+)['\"]", m.group(1))
    return dict(pairs)

def main():
    source = load_json_source()
    py_map = load_python_map()
    ts_map = load_ts_map()
    
    errors = []
    
    for key, val in source.items():
        if key not in py_map:
            errors.append(f"MISSING in Python: {key} -> {val}")
        elif py_map[key] != val:
            errors.append(f"MISMATCH Python: {key}: expected '{val}', got '{py_map[key]}'")
        
        if key not in ts_map:
            errors.append(f"MISSING in TypeScript: {key} -> {val}")
        elif ts_map[key] != val:
            errors.append(f"MISMATCH TypeScript: {key}: expected '{val}', got '{ts_map[key]}'")

    # Check for extras not in source
    for key in py_map:
        if key not in source:
            errors.append(f"EXTRA in Python (not in source): {key}")
    for key in ts_map:
        if key not in source:
            errors.append(f"EXTRA in TypeScript (not in source): {key}")

    if errors:
        print("Action-map sync check FAILED:")
        for e in errors:
            print(f"  ❌ {e}")
        sys.exit(1)
    else:
        print(f"✅ All {len(source)} action mappings in sync across 3 files.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行验证脚本**

```bash
python scripts/sync-action-map.py
```
Expected: `✅ All 42 action mappings in sync across 3 files.`

- [ ] **Step 4: Commit**

```bash
git add shared/action-map.json scripts/sync-action-map.py
git commit -m "feat: action-map 单源 JSON + 一致性验证脚本"
```

---

## Task 6: 录制器 Shadow DOM 基础支持

**Files:**
- Modify: `sidecar/browser/recorder.py` — getSelector 穿越 Shadow DOM

**当前问题：** `getSelector()` 沿 `parentElement` 向上遍历到 `document.body`，不处理 Shadow Root。Shadow DOM 内的元素生成的选择器在外部不可用。

**方案：** 在 `getSelector()` 中检测 `element.getRootNode()` 是否为 ShadowRoot，如果是则生成 `>>> ` 穿透选择器（Playwright 支持 `>>` 作为 Shadow DOM 穿透符）。

- [ ] **Step 1: 修改 RECORDER_JS 中的 getSelector**

替换 `getSelector` 函数：

```javascript
const getSelector = (el) => {
    // Build segments from element up through potential shadow boundaries
    const segments = [];
    let current = el;
    
    while (current && current !== document) {
        // Check if we're inside a Shadow DOM
        const root = current.getRootNode();
        
        // Build selector for current element within its root
        let seg = _selectorInRoot(current, root === document ? document.body : root);
        segments.unshift(seg);
        
        if (root instanceof ShadowRoot) {
            // Cross shadow boundary: find the host element and continue
            segments.unshift('>>');
            current = root.host;
        } else {
            break;
        }
    }
    
    return segments.join(' ');
};

const _selectorInRoot = (el, boundary) => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    if (el.className && typeof el.className === 'string') {
        const cls = el.className.trim().split(/\\s+/).filter(c => c.length > 0);
        if (cls.length > 0) {
            const sel = el.tagName.toLowerCase() + '.' + cls.map(c => CSS.escape(c)).join('.');
            const root = el.getRootNode();
            const searchBase = root === document ? document : root;
            try {
                if (searchBase.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
    }
    // Fallback: nth-of-type path (within current shadow root or document)
    const path = [];
    let cur = el;
    while (cur && cur !== boundary && cur !== document.body && cur !== document.documentElement) {
        let s = cur.tagName.toLowerCase();
        const parent = cur.parentElement;
        if (parent) {
            const siblings = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
            if (siblings.length > 1) {
                const idx = siblings.indexOf(cur) + 1;
                s += ':nth-of-type(' + idx + ')';
            }
        }
        path.unshift(s);
        cur = parent;
    }
    return path.join(' > ');
};
```

注意：对 closed Shadow Root，`getRootNode()` 仍返回 ShadowRoot 但 `.host` 可能不可访问。这是浏览器限制，无法完美解决，但覆盖了 open Shadow DOM（大多数 Web Components 使用 open mode）。

- [ ] **Step 2: 运行现有测试确保不破坏**

```bash
cd sidecar && python -m pytest tests/ --ignore=tests/test_blocks_e2e.py --ignore=tests/test_anti_detect.py -v
```

- [ ] **Step 3: Commit**

```bash
git add sidecar/browser/recorder.py
git commit -m "feat: 录制器 Shadow DOM 穿透选择器支持 (Playwright >> 语法)"
```

---

## 验证清单

完成所有 Task 后，执行完整验证：

```bash
# 1. Python 单元测试
cd sidecar && python -m pytest tests/ --ignore=tests/test_blocks_e2e.py --ignore=tests/test_anti_detect.py -v

# 2. Action-map 一致性
python scripts/sync-action-map.py

# 3. Rust 编译
cd src-tauri && cargo check

# 4. 前端编译
pnpm build
```
