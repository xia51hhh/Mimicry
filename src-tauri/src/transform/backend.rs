use super::action_map::to_backend;
use super::types::*;

/// Convert a Canonical workflow to Backend format for Python executor.
///
/// Transformations:
/// - action: PascalCase → snake_case via action_map
/// - data.children / data.elseChildren → top-level children/elseChildren (recursive)
/// - runtime.sessionId → session_id
/// - Strips position, selected, edges
pub fn canonical_to_backend(
    canonical: &CanonicalWorkflow,
    default_session_id: &str,
) -> Result<BackendWorkflow, TransformError> {
    let nodes = canonical
        .nodes
        .iter()
        .map(|n| convert_node(n, default_session_id))
        .collect::<Result<Vec<_>, _>>()?;

    Ok(BackendWorkflow {
        name: canonical.name.clone().unwrap_or_default(),
        nodes,
    })
}

fn convert_node(
    node: &CanonicalNode,
    default_session_id: &str,
) -> Result<BackendNode, TransformError> {
    let kind_str = node.kind.to_string();

    // Convert action name
    let action = match &node.action {
        Some(a) => to_backend(a),
        None => kind_str.clone(), // condition/group nodes may not have action
    };

    // Extract session_id from runtime
    let session_id = node
        .runtime
        .as_ref()
        .and_then(|r| r.session_id.clone())
        .unwrap_or_else(|| default_session_id.to_string());

    // Extract children and elseChildren from data
    let data_obj = node.data.as_object();
    let children_val = data_obj.and_then(|d| d.get("children"));
    let else_children_val = data_obj.and_then(|d| d.get("elseChildren"));

    let children = extract_children(children_val, default_session_id)?;
    let else_children = extract_children(else_children_val, default_session_id)?;

    // Build clean data without children/elseChildren
    let clean_data = if let Some(obj) = data_obj {
        let mut clean = obj.clone();
        clean.remove("children");
        clean.remove("elseChildren");
        serde_json::Value::Object(clean)
    } else {
        node.data.clone()
    };

    // Convert settings to Value
    let settings = match &node.settings {
        Some(s) => serde_json::to_value(s).unwrap_or(serde_json::Value::Object(Default::default())),
        None => serde_json::Value::Object(Default::default()),
    };

    Ok(BackendNode {
        id: node.id.clone(),
        kind: kind_str.clone(),
        node_type: kind_str,
        action,
        data: clean_data,
        settings,
        session_id,
        children,
        else_children,
    })
}

fn extract_children(
    val: Option<&serde_json::Value>,
    default_session_id: &str,
) -> Result<Vec<BackendNode>, TransformError> {
    match val {
        Some(serde_json::Value::Array(arr)) => arr
            .iter()
            .map(|v| {
                let node: CanonicalNode = serde_json::from_value(v.clone())?;
                convert_node(&node, default_session_id)
            })
            .collect(),
        _ => Ok(vec![]),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn make_canonical(nodes_json: serde_json::Value) -> CanonicalWorkflow {
        CanonicalWorkflow {
            id: Some("wf1".into()),
            name: Some("test".into()),
            nodes: serde_json::from_value(nodes_json).unwrap(),
            edges: vec![],
            created_at: None,
            updated_at: None,
        }
    }

    #[test]
    fn basic_action_conversion() {
        let wf = make_canonical(json!([
            {
                "id": "n1", "kind": "action", "action": "Navigate",
                "position": {"x": 0, "y": 0},
                "data": {"url": "https://example.com"}
            }
        ]));
        let backend = canonical_to_backend(&wf, "default").unwrap();
        assert_eq!(backend.nodes.len(), 1);
        assert_eq!(backend.nodes[0].action, "open");
        assert_eq!(backend.nodes[0].session_id, "default");
        assert_eq!(backend.nodes[0].kind, "action");
        assert_eq!(backend.nodes[0].node_type, "action");
    }

    #[test]
    fn session_id_from_runtime() {
        let wf = make_canonical(json!([
            {
                "id": "n1", "kind": "action", "action": "Click",
                "position": {"x": 0, "y": 0},
                "data": {"selector": "#btn"},
                "runtime": {"sessionId": "browser-2"}
            }
        ]));
        let backend = canonical_to_backend(&wf, "default").unwrap();
        assert_eq!(backend.nodes[0].session_id, "browser-2");
    }

    #[test]
    fn children_extraction() {
        let wf = make_canonical(json!([
            {
                "id": "n1", "kind": "condition", "action": "Condition",
                "position": {"x": 0, "y": 0},
                "data": {
                    "condition": "element_visible",
                    "selector": "#result",
                    "children": [
                        {"id": "c1", "kind": "action", "action": "Click",
                         "position": {"x": 0, "y": 0}, "data": {"selector": "#ok"}}
                    ],
                    "elseChildren": [
                        {"id": "c2", "kind": "action", "action": "Log",
                         "position": {"x": 0, "y": 0}, "data": {"message": "not found"}}
                    ]
                }
            }
        ]));
        let backend = canonical_to_backend(&wf, "default").unwrap();
        let node = &backend.nodes[0];
        assert_eq!(node.children.len(), 1);
        assert_eq!(node.children[0].action, "click");
        assert_eq!(node.else_children.len(), 1);
        assert_eq!(node.else_children[0].action, "log");
        // data should not contain children/elseChildren
        assert!(node.data.get("children").is_none());
        assert!(node.data.get("elseChildren").is_none());
        // but should still have condition/selector
        assert_eq!(node.data["condition"], "element_visible");
    }

    #[test]
    fn condition_without_action() {
        let wf = make_canonical(json!([
            {
                "id": "n1", "kind": "condition",
                "position": {"x": 0, "y": 0},
                "data": {"condition": "element_visible"}
            }
        ]));
        let backend = canonical_to_backend(&wf, "default").unwrap();
        // When action is None, falls back to kind string
        assert_eq!(backend.nodes[0].action, "condition");
    }
}
