# 日志 i18n 规范化

## 目标
统一 sidecar 和前端的日志格式：中文操作 + 英文专有名词混合。

## 规则
- 操作描述用中文：`浏览器已启动`, `录制开始`, `执行工作流`
- 专有名词保留英文：`Camoufox`, `Playwright`, `Session`, `Tab`, `BrowserContext`
- 技术参数保留英文：`PID: 12345`, `URL: https://...`, `selector: #btn`
- 错误消息英文（便于搜索）

## 范围
- sidecar/ 所有 Python logger 调用
- src/stores/ 中的 logEntry 消息
- execution.ts 的 log callback 消息
