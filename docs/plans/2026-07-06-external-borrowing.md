# 外部项目借鉴 — 迭代计划

> **状态**: In Progress | **创建**: 2026-07-06

## 背景

基于对 5 个外部参考项目的分析，提取了 7 个高优先级借鉴点，与用户对齐后确定 4 项改进工作。

### 参考项目

| 项目 | 借鉴重点 |
|------|---------|
| playwright-captcha | 验证码三阶段架构 (Detect→Solve→Apply) |
| camoufox-reverse-mcp | JS Hook 模板分离、持久化注入 |
| WebAI2API | 拟人化操作、三级进程清理、Worker Pool、故障转移 |
| HeadlessX | ONNX 验证码识别、CF Challenge 服务 |

## 决策记录

| # | 改进项 | 决策 | 范围 |
|---|--------|------|------|
| 1 | 验证码系统 | 只搭三阶段框架，不加新类型 | `sidecar/captcha/` |
| 2 | JS 注入管理 | 拆出 RECORDER_JS 到独立 .js 文件 | `sidecar/browser/` |
| 3 | 进程清理 | 加上 close→SIGTERM→SIGKILL 三级清理 | `sidecar/browser/controller.py` |
| 4 | 拟人化操作 | 全面增强：safeClick + humanType + getRealViewport | `sidecar/browser/controller.py` |

执行策略：4 项并行（subagent 分头实现）。

---

## Task 1: 验证码三阶段框架

### 目标
将 `sidecar/captcha/` 重构为 Detect→Solve→Apply 三阶段基类 + Cloudflare 具体实现。

### 改动文件
- **新建** `sidecar/captcha/base.py` — `CaptchaSolver` 抽象基类 (detect/solve/apply)
- **重构** `sidecar/captcha/cloudflare.py` — 继承基类，实现三个阶段
- **更新** `sidecar/captcha/__init__.py` — 导出基类

### 设计
```python
class CaptchaSolver(ABC):
    @abstractmethod
    def detect(self, page: Page) -> dict:
        """检测页面是否有验证码，返回 {detected: bool, type: str, ...}"""

    @abstractmethod
    def solve(self, page: Page, detection: dict) -> dict:
        """尝试解决验证码，返回 {solved: bool, ...}"""

    @abstractmethod
    def apply(self, page: Page, solution: dict) -> dict:
        """应用解决结果，返回 {applied: bool, ...}"""

    def run(self, page: Page) -> dict:
        """三阶段流水线"""
        detection = self.detect(page)
        if not detection.get("detected"):
            return {"status": "no_captcha"}
        solution = self.solve(page, detection)
        if not solution.get("solved"):
            return {"status": "solve_failed", **solution}
        return self.apply(page, solution)
```

---

## Task 2: JS 模板分离

### 目标
将 `recorder.py` 中内嵌的 ~170 行 RECORDER_JS 提取到独立文件。

### 改动文件
- **新建** `sidecar/browser/scripts/recorder.js`
- **修改** `sidecar/browser/recorder.py` — 运行时读取 .js 文件

---

## Task 3: 三级进程清理

### 目标
`controller.py` 的 `close()` 方法增加渐进式退出：close → 等待 → SIGTERM → 等待 → SIGKILL。

### 改动文件
- **修改** `sidecar/browser/controller.py` — `close()` 方法

### 设计
```
1. browser.close() — 正常关闭 (3s 超时)
2. SIGTERM → 等待 3s
3. SIGKILL — 强制终止
```

---

## Task 4: 拟人化操作全面增强

### 目标
在 `controller.py` 增加三个反检测能力：

1. **safe_click** — 点击偏移到元素中心区域（避免精确中心 + 边缘）
2. **human_type 增强** — 变速输入、偶尔退格修正、段落间停顿
3. **get_real_viewport** — 获取真实视口边界，操作不超出可见区域

### 改动文件
- **修改** `sidecar/browser/controller.py` — 新增/增强方法
- **修改** `sidecar/browser/actions.py` — 暴露新方法到 RPC

---

## 与现有设计的兼容性

| ADR | 冲突？ | 说明 |
|-----|--------|------|
| ADR-001 JSON 直驱 | ✅ 无冲突 | 所有改动在 Python sidecar 层，不影响 JSON 节点图 |
| ADR-002 多策略选择器 | ✅ 互补 | safe_click 增强了元素操作可靠性 |
| ADR-003 Loop 模型 | ✅ 无冲突 | 不涉及循环系统 |
| ADR-004 调试体系 | ✅ 无冲突 | 不涉及调试系统 |
| ADR-005 错误处理 | ✅ 互补 | 三级清理和拟人化增强了错误恢复能力 |
| ADR-006 Package | ✅ 无冲突 | 不涉及 Package 系统 |
