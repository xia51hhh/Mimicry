# 工作流中间层 — LLM/CLI 描述格式与画布自动布局

## Goal

设计并实现一套工作流中间层（Interchange Layer），实现以下核心能力：

1. **LLM 友好的描述格式（Compact Format）**：不含 position/edge/视觉元数据，仅包含执行逻辑，便于 LLM 生成和阅读
2. **自动检测文件类型**：导入时自动识别是完整画布文件（Canonical）还是 LLM 描述文件（Compact）
3. **自动布局引擎**：将无位置信息的节点序列自动布局到画布上，生成合理的连接（edges）
4. **双向转换**：Canonical ↔ Compact 无损往返

## 当前状态分析

### 已有格式
| 格式 | 含位置 | 含 edges | 含 settings | action 命名 | 使用场景 |
|------|:------:|:--------:|:-----------:|:-----------:|---------|
| Canonical (画布/DB) | ✓ | ✓ | ✓ | PascalCase | 主文件格式 |
| CLI/E2E 测试 JSON | ✗ | ✗(空数组) | ✗ | snake_case | executor 直接执行 |
| Executor 内部格式 | ✗ | ✗ | ✓ | snake_case | Python 运行时 |

### 已有转换
- `vueNodeToCanonical()` / `canonicalNodeToVue()` — 画布 ↔ Canonical
- `migrateLegacyWorkflow()` — 旧格式 → Canonical
- `executor._normalize_node()` — 任意 → Executor 内部

### 缺失环节
- **Canonical → Compact** — 无专门导出函数，总是带 position
- **Compact → Canonical（含自动布局）** — `fromJSON()` 给无位置节点填 (0,0)，不自动排列
- **LLM 标准描述格式文档** — 无官方 schema 定义
- **自动 edges 生成** — 纯线性序列自动串连 + condition/loop 嵌套推导

## 核心问题（需与用户确认）

1. Compact 格式该用什么命名规范？PascalCase（与画布一致）还是 snake_case（与 executor 一致）？
2. 嵌套结构：condition/loop 的 children/elseChildren 用内联嵌套 JSON 还是平铺 + 引用？
3. 自动布局算法：简单的自上而下线性布局 vs dagre/ELK 图布局？
4. 导入入口在哪里？文件导入按钮 + 粘贴板 + 拖放？
5. LLM 接入方式：是通过 API 直接生成 JSON？还是需要自然语言→JSON 的中间解析？

## Assumptions (temporary)

- Compact 格式应尽量简洁，去除所有视觉信息（position, edge styling, selected 等）
- 保留 kind/action/data/settings 作为核心字段
- 节点 ID 可选（导入时自动生成）
- edges 在 Compact 格式中省略，导入时根据节点顺序和嵌套关系自动生成

## Open Questions

- 见核心问题 1-5

## Requirements (evolving)

- [ ] 定义 Compact Format JSON Schema
- [ ] 实现 `toCompactJSON()` 导出（Canonical → Compact）
- [ ] 实现 `fromCompactJSON()` 导入（Compact → Canonical + 自动布局/连接）
- [ ] 文件类型自动检测（有 position → Canonical，无 → Compact）
- [ ] 自动布局算法
- [ ] 自动 edges 生成
- [ ] LLM 接入格式文档
- [ ] 前端导入 UI 入口

## Acceptance Criteria (evolving)

- [ ] LLM 生成的 Compact JSON 可一键导入为完整画布工作流
- [ ] 画布工作流可导出为 Compact JSON 供 LLM 阅读/修改
- [ ] Canonical → Compact → Canonical 往返后执行语义不变
- [ ] 自动布局结果可读（节点不重叠，边不交叉）
- [ ] E2E 测试 JSON（snake_case）可直接作为 Compact 导入

## Definition of Done

- Tests added/updated (unit/integration where appropriate)
- Lint / typecheck / CI green
- Docs/notes updated if behavior changes

## Out of Scope (explicit)

- 自然语言 → JSON 的 AI 解析（那是 LLM 侧的责任）
- 可视化布局编辑器（拖动调整布局后重新导出）
- 多工作流合并/diff

## Technical Notes

- 工作流类型定义: `src/types/workflow.ts`
- Schema 校验: `src/utils/workflowSchema.ts`（`vueNodeToCanonical`, `canonicalNodeToVue`, `migrateLegacyWorkflow`）
- 文件操作: `src/composables/useFileOps.ts`
- Vue Flow 自动布局: 已有 `autoLayout()` 但需手动调用
- Executor 归一化: `sidecar/engine/executor.py` → `_normalize_node()`
- Action 映射: `shared/action-map.json`
