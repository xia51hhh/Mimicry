# Block 文档全面更新

## 目标
将 docs/block-api.md 从旧 flat 格式更新到 canonical 格式，并补充多浏览器/Tab 交互设计。

## 范围
1. 所有示例从 `{type, action, url}` 更新为 `{kind, action, data: {url}}`
2. 新增 UseBrowser block 文档
3. 新增 WaitForNewTab block 文档
4. SwitchTab/CloseTab 更新为新 Tab 数据结构
5. 补充多浏览器隔离说明（Session = Profile）
6. 补充 Tab 匹配梯度说明

## 关联
- 依赖 Tab 标识系统设计确定
- 依赖 Session 路由方案确定
