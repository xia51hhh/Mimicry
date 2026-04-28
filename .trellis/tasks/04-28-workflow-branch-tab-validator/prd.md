# 工作流分支 Tab 一致性检测器

## 目标
在 Rust 端（src-tauri）实现 workflow JSON 静态分析器，检测分支中 tab 创建/删除数量不一致的情况。

## 规则
- Condition 节点：检查 children 和 elseChildren 中 NewTab/CloseTab 数量是否相等
- Loop 节点：检查 body 中是否有 NewTab/CloseTab（循环中创建 tab 需要特别注意）
- 触发 WARNING 级别检测（不阻止执行）

## 检测输出
```json
{
  "level": "warning",
  "nodeId": "condition_xxx",
  "message": "分支中 Tab 创建数量不一致（true: 2, false: 0），seq 匹配可能不准确，建议使用 URL 作为辅助匹配",
  "suggestion": "在 SwitchTab 中设置 urlOrigin + urlPath"
}
```

## 实现位置
- `src-tauri/src/workflow_validator.rs`（新文件）
- 在 workflow_execute 命令前调用
- 编辑器中实时验证（通过 Tauri 命令）
