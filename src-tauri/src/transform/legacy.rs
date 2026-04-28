use super::action_map::{is_snake_case_action, to_frontend};
use super::types::*;

/// Convert a Legacy flat-format workflow to Canonical format.
///
/// Legacy format characteristics:
/// - Uses `type` instead of `kind`
/// - Action parameters are flat in the node object (not nested in `data`)
/// - Action names may be snake_case or PascalCase
/// - May lack `id`, `position`, `settings`
pub fn legacy_to_canonical(json: &serde_json::Value) -> Result<CanonicalWorkflow, TransformError> {
    let nodes = json
        .get("nodes")
        .and_then(|v| v.as_array())
        .ok_or(TransformError::MissingField {
            node_id: "<root>".into(),
            field: "nodes".into(),
        })?;

    let canonical_nodes: Vec<CanonicalNode> = nodes
        .iter()
        .enumerate()
        .map(|(i, n)| convert_legacy_node(n, i))
        .collect::<Result<Vec<_>, _>>()?;

    // Generate simple sequential edges
    let edges: Vec<CanonicalEdge> = canonical_nodes
        .windows(2)
        .map(|pair| CanonicalEdge {
            id: format!("edge_{}__{}", pair[0].id, pair[1].id),
            source: pair[0].id.clone(),
            target: pair[1].id.clone(),
            source_handle: None,
            target_handle: None,
            label: None,
            extra: Default::default(),
        })
        .collect();

    // Auto-layout
    let config = super::layout::LayoutConfig::default();
    let positions = super::layout::auto_layout(&canonical_nodes, &config);
    let mut canonical_nodes = canonical_nodes;
    for (node, pos) in canonical_nodes.iter_mut().zip(positions.iter()) {
        node.position = pos.clone();
    }

    Ok(CanonicalWorkflow {
        id: json.get("id").and_then(|v| v.as_str()).map(String::from),
        name: json.get("name").and_then(|v| v.as_str()).map(String::from),
        nodes: canonical_nodes,
        edges,
        created_at: None,
        updated_at: None,
    })
}

/// Known metadata fields that should NOT be put into `data`
const META_FIELDS: &[&str] = &[
    "id", "type", "kind", "action", "position", "settings", "runtime",
    "selected", "sessionId", "session_id",
];

fn convert_legacy_node(
    node: &serde_json::Value,
    index: usize,
) -> Result<CanonicalNode, TransformError> {
    let obj = node
        .as_object()
        .ok_or(TransformError::InvalidKind { kind: "non-object node".into() })?;

    // Extract id
    let id = obj
        .get("id")
        .and_then(|v| v.as_str())
        .map(String::from)
        .unwrap_or_else(|| format!("legacy_{index}"));

    // Extract kind from "type" field
    let type_str = obj
        .get("type")
        .and_then(|v| v.as_str())
        .unwrap_or("action");

    let kind = match type_str {
        "action" => NodeKind::Action,
        "condition" => NodeKind::Condition,
        "loop" => NodeKind::Loop,
        "group" => NodeKind::Group,
        other => return Err(TransformError::InvalidKind { kind: other.into() }),
    };

    // Extract and normalize action
    let raw_action = obj.get("action").and_then(|v| v.as_str());
    let action = raw_action.map(|a| {
        if is_snake_case_action(a) {
            to_frontend(a)
        } else {
            a.to_string()
        }
    });

    // Extract position if present
    let position = obj
        .get("position")
        .and_then(|v| serde_json::from_value::<Position>(v.clone()).ok())
        .unwrap_or(Position { x: 0.0, y: 0.0 });

    // Collect non-metadata fields into data
    let mut data = serde_json::Map::new();
    for (key, val) in obj {
        if !META_FIELDS.contains(&key.as_str()) {
            data.insert(key.clone(), val.clone());
        }
    }

    // Extract sessionId → runtime
    let session_id = obj
        .get("sessionId")
        .or_else(|| obj.get("session_id"))
        .and_then(|v| v.as_str())
        .map(String::from);

    let runtime = session_id.map(|sid| NodeRuntime {
        session_id: Some(sid),
        extra: Default::default(),
    });

    // Extract settings if present
    let settings = obj
        .get("settings")
        .and_then(|v| serde_json::from_value::<NodeSettings>(v.clone()).ok());

    Ok(CanonicalNode {
        id,
        kind,
        action,
        position,
        data: serde_json::Value::Object(data),
        settings,
        runtime,
        selected: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn legacy_basic() {
        let wf = json!({
            "name": "test",
            "nodes": [
                {"type": "action", "action": "click", "selector": "#btn"},
                {"type": "action", "action": "Navigate", "url": "https://example.com"}
            ],
            "edges": []
        });

        let canonical = legacy_to_canonical(&wf).unwrap();
        assert_eq!(canonical.nodes.len(), 2);
        // snake_case → PascalCase
        assert_eq!(canonical.nodes[0].action.as_deref(), Some("Click"));
        assert_eq!(canonical.nodes[0].data["selector"], "#btn");
        // Already PascalCase → unchanged
        assert_eq!(canonical.nodes[1].action.as_deref(), Some("Navigate"));
        // Auto-generated edge
        assert_eq!(canonical.edges.len(), 1);
    }

    #[test]
    fn legacy_with_session_id() {
        let wf = json!({
            "nodes": [
                {"type": "action", "action": "click", "selector": "#x", "sessionId": "s1"}
            ]
        });

        let canonical = legacy_to_canonical(&wf).unwrap();
        assert_eq!(
            canonical.nodes[0].runtime.as_ref().unwrap().session_id.as_deref(),
            Some("s1")
        );
    }

    #[test]
    fn legacy_auto_id_and_position() {
        let wf = json!({
            "nodes": [{"type": "action", "action": "click", "selector": "#a"}]
        });

        let canonical = legacy_to_canonical(&wf).unwrap();
        assert!(canonical.nodes[0].id.starts_with("legacy_"));
        assert!(canonical.nodes[0].position.y > 0.0); // auto-layout applied
    }

    #[test]
    fn legacy_missing_nodes() {
        let wf = json!({"name": "test"});
        assert!(legacy_to_canonical(&wf).is_err());
    }
}
