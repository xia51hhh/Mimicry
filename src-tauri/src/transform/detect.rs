use serde_json::Value;

/// Detected workflow format
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkflowFormat {
    /// Full canonical: has position, edges, kind
    Canonical,
    /// Compact: no position, has action, nodes as array
    Compact,
    /// Recording output: has kind, no position, snake_case action
    Recording,
    /// Legacy flat: has type (not kind), flat fields
    Legacy,
    /// Unrecognized
    Unknown,
}

impl std::fmt::Display for WorkflowFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WorkflowFormat::Canonical => write!(f, "canonical"),
            WorkflowFormat::Compact => write!(f, "compact"),
            WorkflowFormat::Recording => write!(f, "recording"),
            WorkflowFormat::Legacy => write!(f, "legacy"),
            WorkflowFormat::Unknown => write!(f, "unknown"),
        }
    }
}

/// Detect the format of a workflow JSON value.
///
/// Detection logic (applied to the first node in the `nodes` array):
/// 1. Has `position` + `kind` + non-empty `edges` → Canonical
/// 2. Has `kind` + no `position` → Recording (snake_case action from recorder)
/// 3. No `position`, has `action` → Compact
/// 4. Has `type` (not `kind`), flat fields → Legacy
/// 5. Otherwise → Unknown
pub fn detect_format(json: &Value) -> WorkflowFormat {
    let nodes = match json.get("nodes") {
        Some(Value::Array(arr)) => arr,
        _ => return WorkflowFormat::Unknown,
    };

    // Empty nodes array — treat as Canonical (valid empty workflow)
    if nodes.is_empty() {
        return WorkflowFormat::Canonical;
    }

    let first = &nodes[0];
    let has_position = first.get("position").is_some();
    let has_kind = first.get("kind").is_some();
    let has_type = first.get("type").is_some();
    let has_action = first.get("action").is_some();
    let has_edges = json
        .get("edges")
        .and_then(|e| e.as_array())
        .is_some_and(|arr| !arr.is_empty());

    if has_kind && has_position {
        // Full canonical format
        WorkflowFormat::Canonical
    } else if has_kind && !has_position {
        // Has kind but no position — recording output
        WorkflowFormat::Recording
    } else if !has_position && has_action && !has_type {
        // No position, has action, no "type" field — compact
        WorkflowFormat::Compact
    } else if has_type && !has_kind {
        // Has "type" but not "kind" — legacy flat format
        WorkflowFormat::Legacy
    } else if has_position && has_edges {
        // Fallback: has position + edges → probably canonical-ish
        WorkflowFormat::Canonical
    } else {
        WorkflowFormat::Unknown
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn detect_canonical() {
        let wf = json!({
            "nodes": [{"id": "1", "kind": "action", "action": "Navigate", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [{"id": "e1", "source": "1", "target": "2"}]
        });
        assert_eq!(detect_format(&wf), WorkflowFormat::Canonical);
    }

    #[test]
    fn detect_canonical_no_edges() {
        let wf = json!({
            "nodes": [{"id": "1", "kind": "action", "action": "Navigate", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": []
        });
        // Has kind + position → Canonical even with empty edges
        assert_eq!(detect_format(&wf), WorkflowFormat::Canonical);
    }

    #[test]
    fn detect_compact() {
        let wf = json!({
            "name": "test",
            "nodes": [{"action": "Navigate", "data": {"url": "https://example.com"}}]
        });
        assert_eq!(detect_format(&wf), WorkflowFormat::Compact);
    }

    #[test]
    fn detect_recording() {
        let wf = json!({
            "name": "Recording",
            "nodes": [{"kind": "action", "action": "click", "data": {"selector": "#btn"}}]
        });
        assert_eq!(detect_format(&wf), WorkflowFormat::Recording);
    }

    #[test]
    fn detect_legacy() {
        let wf = json!({
            "nodes": [{"type": "action", "action": "click", "selector": "#btn"}],
            "edges": []
        });
        assert_eq!(detect_format(&wf), WorkflowFormat::Legacy);
    }

    #[test]
    fn detect_empty_nodes() {
        let wf = json!({"nodes": [], "edges": []});
        assert_eq!(detect_format(&wf), WorkflowFormat::Canonical);
    }

    #[test]
    fn detect_no_nodes() {
        let wf = json!({"name": "test"});
        assert_eq!(detect_format(&wf), WorkflowFormat::Unknown);
    }
}
