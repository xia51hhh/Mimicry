use super::layout::{auto_layout, LayoutConfig};
use super::types::*;
use super::action_map::{is_snake_case_action, to_frontend};

/// Infer NodeKind from action name
fn infer_kind(action: &str) -> (NodeKind, Option<String>) {
    let normalized = if is_snake_case_action(action) {
        to_frontend(action)
    } else {
        action.to_string()
    };

    if normalized == "Condition" || normalized == "ElementExists" {
        (NodeKind::Condition, None) // pseudo-action, no real action
    } else if normalized == "Group" {
        (NodeKind::Group, None)
    } else if normalized.starts_with("Loop") {
        (NodeKind::Loop, Some(normalized))
    } else {
        (NodeKind::Action, Some(normalized))
    }
}

/// Normalize action to PascalCase
fn normalize_action(action: &str) -> String {
    if is_snake_case_action(action) {
        to_frontend(action)
    } else {
        action.to_string()
    }
}

/// Convert a Compact workflow to Canonical format.
///
/// Performs:
/// - kind inference from action name
/// - id generation (uuid)
/// - note → settings.note
/// - auto-layout for positions
/// - auto-generate edges from array order + nesting
/// - snake_case action → PascalCase normalization
pub fn compact_to_canonical(compact: &CompactWorkflow) -> Result<CanonicalWorkflow, TransformError> {
    let config = LayoutConfig::default();

    // First pass: convert nodes and collect for layout
    let mut canonical_nodes = Vec::new();
    let mut edge_pairs: Vec<(String, String)> = Vec::new();

    convert_compact_nodes(&compact.nodes, &mut canonical_nodes, &mut edge_pairs)?;

    // Apply auto-layout
    let positions = auto_layout(&canonical_nodes, &config);
    for (node, pos) in canonical_nodes.iter_mut().zip(positions.iter()) {
        node.position = pos.clone();
    }

    // Generate edges from sequential pairs + nesting
    let edges = edge_pairs
        .iter()
        .map(|(src, tgt)| CanonicalEdge {
            id: format!("edge_{src}__{tgt}"),
            source: src.clone(),
            target: tgt.clone(),
            source_handle: None,
            target_handle: None,
            label: None,
            extra: Default::default(),
        })
        .collect();

    Ok(CanonicalWorkflow {
        id: Some(uuid::Uuid::new_v4().to_string()),
        name: compact.name.clone(),
        nodes: canonical_nodes,
        edges,
        created_at: Some(chrono::Utc::now().to_rfc3339()),
        updated_at: Some(chrono::Utc::now().to_rfc3339()),
    })
}

fn convert_compact_nodes(
    compact_nodes: &[CompactNode],
    out_nodes: &mut Vec<CanonicalNode>,
    out_edges: &mut Vec<(String, String)>,
) -> Result<(), TransformError> {
    let mut prev_id: Option<String> = None;

    for cn in compact_nodes {
        let id = cn
            .id
            .clone()
            .unwrap_or_else(|| format!("node_{}", uuid::Uuid::new_v4().simple()));

        let (inferred_kind, canonical_action) = if let Some(ref k) = cn.kind {
            (k.clone(), Some(normalize_action(&cn.action)))
        } else {
            infer_kind(&cn.action)
        };

        // Build settings from note + existing settings
        let settings = {
            let mut s = cn.settings.clone().unwrap_or_default();
            if let Some(ref note) = cn.note {
                s.note = Some(note.clone());
            }
            Some(s)
        };

        // Build data, embedding children/elseChildren for canonical storage
        let mut data = if cn.data.is_object() {
            cn.data.clone()
        } else {
            serde_json::Value::Object(Default::default())
        };

        // Recursively convert children
        if let Some(ref children) = cn.children {
            let mut child_nodes = Vec::new();
            let mut _child_edges = Vec::new();
            convert_compact_nodes(children, &mut child_nodes, &mut _child_edges)?;
            let children_val: Vec<serde_json::Value> = child_nodes
                .iter()
                .map(|n| serde_json::to_value(n).unwrap())
                .collect();
            data.as_object_mut().unwrap().insert(
                "children".to_string(),
                serde_json::Value::Array(children_val),
            );
        }

        if let Some(ref else_children) = cn.else_children {
            let mut child_nodes = Vec::new();
            let mut _child_edges = Vec::new();
            convert_compact_nodes(else_children, &mut child_nodes, &mut _child_edges)?;
            let children_val: Vec<serde_json::Value> = child_nodes
                .iter()
                .map(|n| serde_json::to_value(n).unwrap())
                .collect();
            data.as_object_mut().unwrap().insert(
                "elseChildren".to_string(),
                serde_json::Value::Array(children_val),
            );
        }

        let node = CanonicalNode {
            id: id.clone(),
            kind: inferred_kind,
            action: canonical_action,
            position: Position { x: 0.0, y: 0.0 }, // placeholder, filled by auto_layout
            data,
            settings,
            runtime: Some(NodeRuntime::default()),
            selected: None,
        };

        // Edge from previous node
        if let Some(ref prev) = prev_id {
            out_edges.push((prev.clone(), id.clone()));
        }

        prev_id = Some(id);
        out_nodes.push(node);
    }

    Ok(())
}

/// Convert a Canonical workflow to Compact format.
///
/// Strips: position, edges, runtime, selected
/// Promotes: settings.note → top-level note
pub fn canonical_to_compact(canonical: &CanonicalWorkflow) -> Result<CompactWorkflow, TransformError> {
    let nodes = canonical
        .nodes
        .iter()
        .map(canonical_node_to_compact)
        .collect::<Result<Vec<_>, _>>()?;

    Ok(CompactWorkflow {
        name: Some(canonical.name.clone().unwrap_or_else(|| "Untitled".into())),
        description: None,
        nodes,
    })
}

fn canonical_node_to_compact(node: &CanonicalNode) -> Result<CompactNode, TransformError> {
    // Determine action string: use action field, or capitalize kind for pseudo-actions
    let action = node
        .action
        .clone()
        .unwrap_or_else(|| match node.kind {
            NodeKind::Condition => "Condition".into(),
            NodeKind::Loop => "Loop".into(),
            NodeKind::Group => "Group".into(),
            NodeKind::Action => "Action".into(),
        });

    // Extract note from settings
    let note = node.settings.as_ref().and_then(|s| s.note.clone());

    // Build settings without note (avoid duplication)
    let settings = node.settings.as_ref().map(|s| {
        let mut clean = s.clone();
        clean.note = None;
        clean
    }).filter(|s| {
        // Only include if there are meaningful settings beyond defaults
        s.on_error.is_some()
            || s.disabled.is_some_and(|d| d)
            || s.retry_on_fail.is_some()
            || s.retry_count.is_some()
            || s.retry_interval.is_some()
            || !s.extra.is_empty()
    });

    // Extract children from data
    let data_obj = node.data.as_object();
    let children = data_obj
        .and_then(|d| d.get("children"))
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| {
                    let cn: CanonicalNode = serde_json::from_value(v.clone()).ok()?;
                    canonical_node_to_compact(&cn).ok()
                })
                .collect::<Vec<_>>()
        })
        .filter(|v| !v.is_empty());

    let else_children = data_obj
        .and_then(|d| d.get("elseChildren"))
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| {
                    let cn: CanonicalNode = serde_json::from_value(v.clone()).ok()?;
                    canonical_node_to_compact(&cn).ok()
                })
                .collect::<Vec<_>>()
        })
        .filter(|v| !v.is_empty());

    // Clean data: remove children/elseChildren
    let clean_data = if let Some(obj) = data_obj {
        let mut clean = obj.clone();
        clean.remove("children");
        clean.remove("elseChildren");
        serde_json::Value::Object(clean)
    } else {
        node.data.clone()
    };

    Ok(CompactNode {
        action,
        data: clean_data,
        note,
        settings,
        children,
        else_children,
        id: None,
        kind: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn compact_to_canonical_basic() {
        let compact = CompactWorkflow {
            name: Some("test".into()),
            description: None,
            nodes: vec![
                CompactNode {
                    action: "Navigate".into(),
                    data: json!({"url": "https://example.com"}),
                    note: Some("go to site".into()),
                    settings: None,
                    children: None,
                    else_children: None,
                    id: None,
                    kind: None,
                },
                CompactNode {
                    action: "Click".into(),
                    data: json!({"selector": "#btn"}),
                    note: None,
                    settings: None,
                    children: None,
                    else_children: None,
                    id: None,
                    kind: None,
                },
            ],
        };

        let canonical = compact_to_canonical(&compact).unwrap();
        assert_eq!(canonical.nodes.len(), 2);
        assert_eq!(canonical.nodes[0].kind, NodeKind::Action);
        assert_eq!(canonical.nodes[0].action.as_deref(), Some("Navigate"));
        assert_eq!(
            canonical.nodes[0].settings.as_ref().unwrap().note.as_deref(),
            Some("go to site")
        );
        // Should have 1 edge connecting node 0 → node 1
        assert_eq!(canonical.edges.len(), 1);
    }

    #[test]
    fn compact_snake_case_normalized() {
        let compact = CompactWorkflow {
            name: Some("test".into()),
            description: None,
            nodes: vec![CompactNode {
                action: "click".into(), // snake_case
                data: json!({"selector": "#btn"}),
                note: None,
                settings: None,
                children: None,
                else_children: None,
                id: None,
                kind: None,
            }],
        };

        let canonical = compact_to_canonical(&compact).unwrap();
        assert_eq!(canonical.nodes[0].action.as_deref(), Some("Click"));
    }

    #[test]
    fn compact_condition_infers_kind() {
        let compact = CompactWorkflow {
            name: Some("test".into()),
            description: None,
            nodes: vec![CompactNode {
                action: "Condition".into(),
                data: json!({"condition": "element_visible", "selector": "#x"}),
                note: None,
                settings: None,
                children: Some(vec![CompactNode {
                    action: "Click".into(),
                    data: json!({"selector": "#ok"}),
                    note: None,
                    settings: None,
                    children: None,
                    else_children: None,
                    id: None,
                    kind: None,
                }]),
                else_children: None,
                id: None,
                kind: None,
            }],
        };

        let canonical = compact_to_canonical(&compact).unwrap();
        assert_eq!(canonical.nodes[0].kind, NodeKind::Condition);
        assert!(canonical.nodes[0].action.is_none()); // pseudo-action stripped
        // children should be in data
        assert!(canonical.nodes[0].data.get("children").is_some());
    }

    #[test]
    fn canonical_to_compact_roundtrip_semantics() {
        let compact = CompactWorkflow {
            name: Some("test".into()),
            description: None,
            nodes: vec![
                CompactNode {
                    action: "Navigate".into(),
                    data: json!({"url": "https://example.com"}),
                    note: Some("step 1".into()),
                    settings: None,
                    children: None,
                    else_children: None,
                    id: None,
                    kind: None,
                },
                CompactNode {
                    action: "Click".into(),
                    data: json!({"selector": "#btn"}),
                    note: None,
                    settings: None,
                    children: None,
                    else_children: None,
                    id: None,
                    kind: None,
                },
            ],
        };

        let canonical = compact_to_canonical(&compact).unwrap();
        let roundtrip = canonical_to_compact(&canonical).unwrap();

        assert_eq!(roundtrip.nodes.len(), 2);
        assert_eq!(roundtrip.nodes[0].action, "Navigate");
        assert_eq!(roundtrip.nodes[0].data["url"], "https://example.com");
        assert_eq!(roundtrip.nodes[0].note.as_deref(), Some("step 1"));
        assert_eq!(roundtrip.nodes[1].action, "Click");
    }
}
