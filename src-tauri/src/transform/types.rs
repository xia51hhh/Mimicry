use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Node kind — matches frontend WorkflowNodeKind
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum NodeKind {
    Action,
    Condition,
    Loop,
    Group,
}

impl std::fmt::Display for NodeKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            NodeKind::Action => write!(f, "action"),
            NodeKind::Condition => write!(f, "condition"),
            NodeKind::Loop => write!(f, "loop"),
            NodeKind::Group => write!(f, "group"),
        }
    }
}

/// Canvas position
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub x: f64,
    pub y: f64,
}

/// Node settings
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NodeSettings {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub on_error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub disabled: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry_on_fail: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry_count: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub retry_interval: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// Runtime configuration
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NodeRuntime {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

// ─── Canonical Format ────────────────────────────────────────────

/// Canonical node — DB persistence & IPC transport format
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanonicalNode {
    pub id: String,
    pub kind: NodeKind,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
    pub position: Position,
    #[serde(default)]
    pub data: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub settings: Option<NodeSettings>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub runtime: Option<NodeRuntime>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub selected: Option<bool>,
}

/// Canonical edge
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanonicalEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_handle: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target_handle: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    /// Vue Flow rendering metadata passthrough
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

/// Canonical workflow — full document.
/// Fields are optional where the execution path doesn't require them.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanonicalWorkflow {
    #[serde(default)]
    pub id: Option<String>,
    #[serde(default)]
    pub name: Option<String>,
    pub nodes: Vec<CanonicalNode>,
    #[serde(default)]
    pub edges: Vec<CanonicalEdge>,
    #[serde(default)]
    pub created_at: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

// ─── Compact Format ──────────────────────────────────────────────

/// Compact node — LLM/CLI description format
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CompactNode {
    pub action: String,
    #[serde(default)]
    pub data: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub settings: Option<NodeSettings>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub children: Option<Vec<CompactNode>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub else_children: Option<Vec<CompactNode>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind: Option<NodeKind>,
}

/// Compact workflow — minimal description document
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompactWorkflow {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub nodes: Vec<CompactNode>,
}

// ─── Backend Format ──────────────────────────────────────────────

/// Backend node — Python executor consumes directly
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendNode {
    pub id: String,
    pub kind: String,
    #[serde(rename = "type")]
    pub node_type: String,
    pub action: String,
    pub data: serde_json::Value,
    #[serde(default)]
    pub settings: serde_json::Value,
    pub session_id: String,
    #[serde(default)]
    pub children: Vec<BackendNode>,
    #[serde(default, rename = "elseChildren")]
    pub else_children: Vec<BackendNode>,
}

/// Backend workflow — sent to Python sidecar
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendWorkflow {
    pub name: String,
    pub nodes: Vec<BackendNode>,
}

// ─── Error ───────────────────────────────────────────────────────

#[derive(Debug, thiserror::Error)]
pub enum TransformError {
    #[error("Unknown workflow format")]
    UnknownFormat,

    #[error("Missing required field '{field}' in node '{node_id}'")]
    MissingField { node_id: String, field: String },

    #[error("Unknown action: {action}")]
    UnknownAction { action: String },

    #[error("Invalid node kind: {kind}")]
    InvalidKind { kind: String },

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Layout error: {0}")]
    Layout(String),
}

impl From<TransformError> for crate::AppError {
    fn from(e: TransformError) -> Self {
        crate::AppError::Transform(e.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn node_kind_serializes_lowercase() {
        assert_eq!(
            serde_json::to_string(&NodeKind::Action).unwrap(),
            "\"action\""
        );
        assert_eq!(
            serde_json::to_string(&NodeKind::Condition).unwrap(),
            "\"condition\""
        );
    }

    #[test]
    fn canonical_workflow_optional_fields() {
        let json = r#"{"nodes":[]}"#;
        let wf: CanonicalWorkflow = serde_json::from_str(json).unwrap();
        assert!(wf.id.is_none());
        assert!(wf.name.is_none());
        assert!(wf.edges.is_empty());
    }

    #[test]
    fn compact_node_roundtrip() {
        let json = r##"{"action":"Click","data":{"selector":"#btn"}}"##;
        let node: CompactNode = serde_json::from_str(json).unwrap();
        assert_eq!(node.action, "Click");
        assert!(node.children.is_none());
    }
}
