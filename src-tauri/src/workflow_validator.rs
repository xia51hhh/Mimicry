use serde::Serialize;
use serde_json::Value;

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DiagLevel {
    Error,
    Warning,
    Info,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Diagnostic {
    pub level: DiagLevel,
    pub rule_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub node_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub suggestion: Option<String>,
}

/// Valid PascalCase action names (from shared/action-map.json).
const VALID_ACTIONS: &[&str] = &[
    "Navigate", "NewTab", "SwitchTab", "CloseTab", "GoBack", "GoForward", "Reload",
    "Click", "DblClick", "Type", "Hover", "Scroll", "SelectOption", "PressKey",
    "Clear", "Focus", "Wait", "GetText", "GetAttribute", "GetURL", "Screenshot",
    "ExtractTable", "SetVariable", "Export", "RunScript", "HttpRequest", "Delay",
    "Log", "Comment", "HandleDialog", "UploadFile", "SwitchFrame", "WaitForPage",
    "Cookie", "ElementExists", "LoopElements", "LoopBreakpoint", "WaitConnections",
    "ExecuteWorkflow", "HandleDownload", "Transform", "Stop", "Fail",
];

const SELECTOR_ACTIONS: &[&str] = &[
    "Click", "DblClick", "Type", "Clear", "Hover", "Focus", "SelectOption",
    "GetText", "GetAttribute", "ExtractTable", "ElementExists", "UploadFile",
];

const URL_ACTIONS: &[&str] = &["Navigate", "HttpRequest"];

/// Validate a workflow JSON and return diagnostics.
/// `workflow` is the full `{name, nodes, edges}` object.
pub fn validate(workflow: &Value) -> Vec<Diagnostic> {
    let mut diags = Vec::new();
    if let Some(nodes) = workflow.get("nodes").and_then(Value::as_array) {
        validate_nodes(nodes, &mut diags, false);
    }
    diags
}

/// Returns true if any diagnostic is Error level.
pub fn has_errors(diags: &[Diagnostic]) -> bool {
    diags.iter().any(|d| d.level == DiagLevel::Error)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

fn validate_nodes(nodes: &[Value], diags: &mut Vec<Diagnostic>, in_loop: bool) {
    for node in nodes {
        validate_node(node, diags, in_loop);
    }
}

fn validate_node(node: &Value, diags: &mut Vec<Diagnostic>, in_loop: bool) {
    let kind = str_field(node, "kind");
    let action = str_field(node, "action");
    let node_id = node.get("id").and_then(Value::as_str).map(String::from);
    let data = node.get("data").unwrap_or(&Value::Null);

    match kind {
        "action" => validate_action_node(&node_id, action, data, diags),
        "condition" => validate_condition_node(&node_id, data, diags, in_loop),
        "loop" => validate_loop_node(&node_id, data, diags),
        _ => {}
    }

    // W012: LoopBreakpoint outside loop
    if kind == "action" && action == "LoopBreakpoint" && !in_loop {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W012".into(),
            node_id: node_id.clone(),
            action: Some("LoopBreakpoint".into()),
            message: "LoopBreakpoint 不在 Loop 内部".into(),
            suggestion: Some("将 LoopBreakpoint 移动到 Loop 的 children 中".into()),
        });
    }
}

// ---------------------------------------------------------------------------
// Action node: E001-E006, E010, E011
// ---------------------------------------------------------------------------

fn validate_action_node(
    node_id: &Option<String>,
    action: &str,
    data: &Value,
    diags: &mut Vec<Diagnostic>,
) {
    // E011: Unknown action
    if !action.is_empty() && !VALID_ACTIONS.contains(&action) {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E011".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: format!("未知的 action 类型 \"{}\"", action),
            suggestion: Some("检查拼写或查阅 action-map.json".into()),
        });
        return; // skip field checks for unknown actions
    }

    // E001: Missing selector
    if SELECTOR_ACTIONS.contains(&action) && is_empty_str(data, "selector") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E001".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: format!("\"{}\" 节点缺少必填字段 \"selector\"", action),
            suggestion: Some("添加 CSS 选择器或 text= 选择器".into()),
        });
    }

    // E002: Missing url
    if URL_ACTIONS.contains(&action) && is_empty_str(data, "url") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E002".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: format!("\"{}\" 节点缺少必填字段 \"url\"", action),
            suggestion: Some("填写目标 URL".into()),
        });
    }

    // E003: Missing key
    if action == "PressKey" && is_empty_str(data, "key") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E003".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"PressKey\" 节点缺少必填字段 \"key\"".into(),
            suggestion: Some("指定按键名称，如 \"Enter\"、\"Tab\"".into()),
        });
    }

    // E004: Missing script
    if action == "RunScript" && is_empty_str(data, "script") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E004".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"RunScript\" 节点缺少必填字段 \"script\"".into(),
            suggestion: Some("编写 JavaScript 脚本内容".into()),
        });
    }

    // E005: Missing variable
    if action == "SetVariable" && is_empty_str(data, "variable") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E005".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"SetVariable\" 节点缺少必填字段 \"variable\"".into(),
            suggestion: Some("指定变量名".into()),
        });
    }

    // E006: Missing filePath
    if action == "UploadFile" && is_empty_str(data, "filePath") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E006".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"UploadFile\" 节点缺少必填字段 \"filePath\"".into(),
            suggestion: Some("选择要上传的文件路径".into()),
        });
    }

    // E010: HttpRequest URL invalid protocol
    if action == "HttpRequest" && !is_empty_str(data, "url") {
        let url = data.get("url").and_then(Value::as_str).unwrap_or("");
        if !url.starts_with("http://")
            && !url.starts_with("https://")
            && !url.contains("{{")
        {
            diags.push(Diagnostic {
                level: DiagLevel::Error,
                rule_id: "E010".into(),
                node_id: node_id.clone(),
                action: Some(action.into()),
                message: format!("HttpRequest URL 缺少有效协议: \"{}\"", url),
                suggestion: Some("URL 应以 http:// 或 https:// 开头".into()),
            });
        }
    }

    // W011: GetAttribute missing attrName
    if action == "GetAttribute" && is_empty_str(data, "attrName") {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W011".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"GetAttribute\" 缺少 \"attrName\" 字段".into(),
            suggestion: Some("指定要提取的属性名，如 \"href\"、\"src\"".into()),
        });
    }

    // W015: ExecuteWorkflow missing workflow reference
    if action == "ExecuteWorkflow" && is_empty_str(data, "workflow") {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W015".into(),
            node_id: node_id.clone(),
            action: Some(action.into()),
            message: "\"ExecuteWorkflow\" 缺少 \"workflow\" 引用".into(),
            suggestion: Some("选择要执行的子工作流".into()),
        });
    }
}

// ---------------------------------------------------------------------------
// Condition node: E009, W008, W002
// ---------------------------------------------------------------------------

fn validate_condition_node(
    node_id: &Option<String>,
    data: &Value,
    diags: &mut Vec<Diagnostic>,
    in_loop: bool,
) {
    // E009: Missing condition expression
    if is_empty_str(data, "condition") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E009".into(),
            node_id: node_id.clone(),
            action: None,
            message: "Condition 节点缺少条件表达式".into(),
            suggestion: Some("填写条件表达式，如 \"$count > 0\"".into()),
        });
    }

    let children = data.get("children").and_then(Value::as_array);
    let else_children = data.get("elseChildren").and_then(Value::as_array);

    // W008: Empty branches
    if children.is_none_or(|c| c.is_empty()) {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W008".into(),
            node_id: node_id.clone(),
            action: None,
            message: "Condition 的 true 分支为空".into(),
            suggestion: None,
        });
    }
    if else_children.is_none_or(|c| c.is_empty()) {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W008".into(),
            node_id: node_id.clone(),
            action: None,
            message: "Condition 的 false 分支为空".into(),
            suggestion: None,
        });
    }

    // W002: Tab asymmetry between branches
    let true_new = children.map_or(0, |c| count_actions(c, "NewTab"));
    let true_close = children.map_or(0, |c| count_actions(c, "CloseTab"));
    let false_new = else_children.map_or(0, |c| count_actions(c, "NewTab"));
    let false_close = else_children.map_or(0, |c| count_actions(c, "CloseTab"));
    if true_new != false_new || true_close != false_close {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W002".into(),
            node_id: node_id.clone(),
            action: None,
            message: format!(
                "分支 Tab 操作不对称 — true: +{}/-{}, false: +{}/-{}",
                true_new, true_close, false_new, false_close
            ),
            suggestion: Some(
                "建议在 SwitchTab 中使用 urlOrigin/urlPath 辅助匹配".into(),
            ),
        });
    }

    // Recurse into children
    if let Some(c) = children {
        validate_nodes(c, diags, in_loop);
    }
    if let Some(c) = else_children {
        validate_nodes(c, diags, in_loop);
    }
}

// ---------------------------------------------------------------------------
// Loop node: E007, E008, W009, W003
// ---------------------------------------------------------------------------

fn validate_loop_node(
    node_id: &Option<String>,
    data: &Value,
    diags: &mut Vec<Diagnostic>,
) {
    let loop_type = str_field(data, "loopType");

    // E007: Loop items/elements missing selector
    if (loop_type == "items" || loop_type == "elements") && is_empty_str(data, "selector") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E007".into(),
            node_id: node_id.clone(),
            action: None,
            message: format!("Loop({}) 缺少必填字段 \"selector\"", loop_type),
            suggestion: Some("指定要遍历的元素选择器".into()),
        });
    }

    // E008: While loop missing condition
    if loop_type == "while" && is_empty_str(data, "whileCondition") {
        diags.push(Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E008".into(),
            node_id: node_id.clone(),
            action: None,
            message: "While Loop 缺少 \"whileCondition\" 条件表达式".into(),
            suggestion: Some("填写循环条件，如 \"$hasNext == true\"".into()),
        });
    }

    let children = data.get("children").and_then(Value::as_array);

    // W009: Empty loop body
    if children.is_none_or(|c| c.is_empty()) {
        diags.push(Diagnostic {
            level: DiagLevel::Warning,
            rule_id: "W009".into(),
            node_id: node_id.clone(),
            action: None,
            message: "Loop 循环体为空".into(),
            suggestion: None,
        });
    }

    // W003: Tab leak in loop (NewTab without CloseTab)
    if let Some(c) = children {
        let new_tabs = count_actions(c, "NewTab");
        let close_tabs = count_actions(c, "CloseTab");
        if new_tabs > close_tabs {
            diags.push(Diagnostic {
                level: DiagLevel::Warning,
                rule_id: "W003".into(),
                node_id: node_id.clone(),
                action: None,
                message: format!(
                    "Loop 内 NewTab({}) > CloseTab({})，可能导致 Tab 泄漏",
                    new_tabs, close_tabs
                ),
                suggestion: Some("在循环体末尾添加 CloseTab 节点".into()),
            });
        }
    }

    // W004: SwitchTab seq out of range
    if let Some(c) = children {
        let max_new_tabs = count_actions(c, "NewTab");
        check_seq_range(c, max_new_tabs, diags);
    }

    // Recurse into children (in_loop = true)
    if let Some(c) = children {
        validate_nodes(c, diags, true);
    }
}

// ---------------------------------------------------------------------------
// Tree-walk helpers
// ---------------------------------------------------------------------------

/// Count how many action nodes of `target_action` appear in a flat+nested node list.
fn count_actions(nodes: &[Value], target_action: &str) -> usize {
    let mut count = 0;
    for node in nodes {
        let action = str_field(node, "action");
        if action == target_action {
            count += 1;
        }
        let data = node.get("data").unwrap_or(&Value::Null);
        if let Some(c) = data.get("children").and_then(Value::as_array) {
            count += count_actions(c, target_action);
        }
        if let Some(c) = data.get("elseChildren").and_then(Value::as_array) {
            count += count_actions(c, target_action);
        }
    }
    count
}

/// W004: Check SwitchTab seq values against known NewTab count.
fn check_seq_range(nodes: &[Value], max_new_tabs: usize, diags: &mut Vec<Diagnostic>) {
    for node in nodes {
        let action = str_field(node, "action");
        if action == "SwitchTab" {
            let data = node.get("data").unwrap_or(&Value::Null);
            if let Some(seq) = data.get("seq").and_then(Value::as_u64) {
                // seq starts from 1; initial tab is seq=1, first NewTab produces seq=2
                if seq as usize > max_new_tabs + 1 {
                    diags.push(Diagnostic {
                        level: DiagLevel::Warning,
                        rule_id: "W004".into(),
                        node_id: node.get("id").and_then(Value::as_str).map(String::from),
                        action: Some("SwitchTab".into()),
                        message: format!(
                            "SwitchTab seq={} 超出范围（当前上下文最多 {} 个 Tab）",
                            seq,
                            max_new_tabs + 1
                        ),
                        suggestion: Some("检查 seq 是否正确，或使用 URL 匹配".into()),
                    });
                }
            }
        }
        let data = node.get("data").unwrap_or(&Value::Null);
        if let Some(c) = data.get("children").and_then(Value::as_array) {
            check_seq_range(c, max_new_tabs, diags);
        }
        if let Some(c) = data.get("elseChildren").and_then(Value::as_array) {
            check_seq_range(c, max_new_tabs, diags);
        }
    }
}

// ---------------------------------------------------------------------------
// Primitive helpers
// ---------------------------------------------------------------------------

fn str_field<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(Value::as_str).unwrap_or("")
}

fn is_empty_str(v: &Value, key: &str) -> bool {
    match v.get(key) {
        None | Some(Value::Null) => true,
        Some(s) => s.as_str().is_some_and(|s| s.trim().is_empty()),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn make_action(id: &str, action: &str, data: Value) -> Value {
        json!({
            "id": id,
            "kind": "action",
            "action": action,
            "data": data
        })
    }

    fn make_workflow(nodes: Vec<Value>) -> Value {
        json!({ "name": "test", "nodes": nodes, "edges": [] })
    }

    #[test]
    fn empty_workflow_ok() {
        let wf = make_workflow(vec![]);
        let diags = validate(&wf);
        assert!(diags.is_empty());
    }

    #[test]
    fn valid_click_no_errors() {
        let wf = make_workflow(vec![
            make_action("n1", "Click", json!({"selector": "#btn"})),
        ]);
        let diags = validate(&wf);
        assert!(diags.is_empty());
    }

    // ── E001: missing selector ──────────────────────────────────────────

    #[test]
    fn e001_missing_selector() {
        let wf = make_workflow(vec![
            make_action("n1", "Click", json!({})),
            make_action("n2", "Type", json!({"value": "hello"})),
        ]);
        let diags = validate(&wf);
        let e001: Vec<_> = diags.iter().filter(|d| d.rule_id == "E001").collect();
        assert_eq!(e001.len(), 2);
        assert!(has_errors(&diags));
    }

    // ── E002: missing url ───────────────────────────────────────────────

    #[test]
    fn e002_missing_url() {
        let wf = make_workflow(vec![
            make_action("n1", "Navigate", json!({})),
        ]);
        let diags: Vec<_> = validate(&wf).into_iter().filter(|d| d.rule_id == "E002").collect();
        assert_eq!(diags.len(), 1);
    }

    // ── E003: missing key ───────────────────────────────────────────────

    #[test]
    fn e003_missing_key() {
        let wf = make_workflow(vec![
            make_action("n1", "PressKey", json!({})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E003"));
    }

    // ── E004: missing script ────────────────────────────────────────────

    #[test]
    fn e004_missing_script() {
        let wf = make_workflow(vec![
            make_action("n1", "RunScript", json!({})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E004"));
    }

    // ── E005: missing variable ──────────────────────────────────────────

    #[test]
    fn e005_missing_variable() {
        let wf = make_workflow(vec![
            make_action("n1", "SetVariable", json!({})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E005"));
    }

    // ── E006: missing filePath ──────────────────────────────────────────

    #[test]
    fn e006_missing_filepath() {
        let wf = make_workflow(vec![
            make_action("n1", "UploadFile", json!({})),
        ]);
        let diags = validate(&wf);
        // E001 (selector) + E006 (filePath)
        assert!(diags.iter().any(|d| d.rule_id == "E001"));
        assert!(diags.iter().any(|d| d.rule_id == "E006"));
    }

    // ── E007: Loop items/elements missing selector ──────────────────────

    #[test]
    fn e007_loop_items_missing_selector() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": { "loopType": "items", "children": [] }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E007"));
    }

    // ── E008: While loop missing condition ──────────────────────────────

    #[test]
    fn e008_while_loop_missing_condition() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": { "loopType": "while", "children": [] }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E008"));
    }

    // ── E009: Condition missing expression ──────────────────────────────

    #[test]
    fn e009_condition_missing_expression() {
        let wf = make_workflow(vec![json!({
            "id": "c1", "kind": "condition",
            "data": { "children": [], "elseChildren": [] }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E009"));
    }

    // ── E010: HttpRequest invalid protocol ──────────────────────────────

    #[test]
    fn e010_http_invalid_protocol() {
        let wf = make_workflow(vec![
            make_action("n1", "HttpRequest", json!({"url": "ftp://example.com"})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "E010"));
    }

    #[test]
    fn e010_template_url_ok() {
        let wf = make_workflow(vec![
            make_action("n1", "HttpRequest", json!({"url": "{{baseUrl}}/api"})),
        ]);
        assert!(!validate(&wf).iter().any(|d| d.rule_id == "E010"));
    }

    // ── E011: Unknown action ────────────────────────────────────────────

    #[test]
    fn e011_unknown_action() {
        let wf = make_workflow(vec![
            make_action("n1", "DoSomethingWeird", json!({})),
        ]);
        let diags: Vec<_> = validate(&wf).into_iter().filter(|d| d.rule_id == "E011").collect();
        assert_eq!(diags.len(), 1);
    }

    // ── W002: Tab asymmetry in condition ────────────────────────────────

    #[test]
    fn w002_tab_asymmetry() {
        let wf = make_workflow(vec![json!({
            "id": "c1", "kind": "condition",
            "data": {
                "condition": "$x > 0",
                "children": [
                    { "id": "n1", "kind": "action", "action": "NewTab", "data": {"url": "https://a.com"} }
                ],
                "elseChildren": []
            }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W002"));
    }

    // ── W003: Tab leak in loop ──────────────────────────────────────────

    #[test]
    fn w003_tab_leak_in_loop() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": {
                "loopType": "count", "count": 5,
                "children": [
                    { "id": "n1", "kind": "action", "action": "NewTab", "data": {} }
                ]
            }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W003"));
    }

    // ── W004: SwitchTab seq out of range ────────────────────────────────

    #[test]
    fn w004_seq_out_of_range() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": {
                "loopType": "count", "count": 5,
                "children": [
                    { "id": "n1", "kind": "action", "action": "SwitchTab", "data": {"seq": 5} }
                ]
            }
        })]);
        // No NewTab in loop, so max_new_tabs=0, seq=5 > 0+1
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W004"));
    }

    // ── W008: Empty condition branches ──────────────────────────────────

    #[test]
    fn w008_empty_branches() {
        let wf = make_workflow(vec![json!({
            "id": "c1", "kind": "condition",
            "data": { "condition": "true", "children": [], "elseChildren": [] }
        })]);
        let w008: Vec<_> = validate(&wf).into_iter().filter(|d| d.rule_id == "W008").collect();
        assert_eq!(w008.len(), 2); // both branches empty
    }

    // ── W009: Empty loop body ───────────────────────────────────────────

    #[test]
    fn w009_empty_loop() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": { "loopType": "count", "count": 3, "children": [] }
        })]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W009"));
    }

    // ── W012: LoopBreakpoint outside loop ───────────────────────────────

    #[test]
    fn w012_breakpoint_outside_loop() {
        let wf = make_workflow(vec![
            make_action("n1", "LoopBreakpoint", json!({})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W012"));
    }

    #[test]
    fn w012_breakpoint_inside_loop_ok() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": {
                "loopType": "count", "count": 3,
                "children": [
                    { "id": "n1", "kind": "action", "action": "LoopBreakpoint", "data": {} }
                ]
            }
        })]);
        assert!(!validate(&wf).iter().any(|d| d.rule_id == "W012"));
    }

    // ── W011: GetAttribute missing attrName ─────────────────────────────

    #[test]
    fn w011_missing_attr_name() {
        let wf = make_workflow(vec![
            make_action("n1", "GetAttribute", json!({"selector": "#el"})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W011"));
    }

    // ── W015: ExecuteWorkflow missing reference ─────────────────────────

    #[test]
    fn w015_missing_workflow_ref() {
        let wf = make_workflow(vec![
            make_action("n1", "ExecuteWorkflow", json!({})),
        ]);
        assert!(validate(&wf).iter().any(|d| d.rule_id == "W015"));
    }

    // ── Nested: condition inside loop propagates in_loop ────────────────

    #[test]
    fn nested_breakpoint_in_loop_condition_ok() {
        let wf = make_workflow(vec![json!({
            "id": "l1", "kind": "loop",
            "data": {
                "loopType": "count", "count": 3,
                "children": [json!({
                    "id": "c1", "kind": "condition",
                    "data": {
                        "condition": "$i > 2",
                        "children": [
                            { "id": "n1", "kind": "action", "action": "LoopBreakpoint", "data": {} }
                        ],
                        "elseChildren": []
                    }
                })]
            }
        })]);
        assert!(!validate(&wf).iter().any(|d| d.rule_id == "W012"));
    }

    // ── Serialization ───────────────────────────────────────────────────

    #[test]
    fn diagnostic_serializes_camel_case() {
        let d = Diagnostic {
            level: DiagLevel::Error,
            rule_id: "E001".into(),
            node_id: Some("n1".into()),
            action: Some("Click".into()),
            message: "test".into(),
            suggestion: None,
        };
        let json = serde_json::to_value(&d).unwrap();
        assert_eq!(json["ruleId"], "E001");
        assert_eq!(json["nodeId"], "n1");
        assert_eq!(json["level"], "error");
        assert!(json.get("suggestion").is_none());
    }
}
