# 日志面板增强

## 功能
1. **一键复制全部日志**：工具栏增加复制按钮（📋），复制全部日志到剪贴板
2. **右键菜单复制**：日志区域右键 → 复制选中/全部
3. **日志格式**：`[HH:mm:ss] LEVEL (nodeId) message`

## 实现
- BottomPanel.vue：添加复制按钮 + 右键菜单
- i18n：添加 `bottomPanel.copyLogs`, `bottomPanel.copySuccess` 等 key
- 使用 Tauri clipboard API 或 navigator.clipboard
