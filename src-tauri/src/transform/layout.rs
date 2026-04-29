use super::types::*;

/// Layout configuration
pub struct LayoutConfig {
    pub start_x: f64,
    pub start_y: f64,
    pub y_gap: f64,
}

impl Default for LayoutConfig {
    fn default() -> Self {
        Self {
            start_x: 300.0,
            start_y: 100.0,
            y_gap: 120.0,
        }
    }
}

/// Generate positions for a flat list of canonical nodes using simple
/// top-down linear layout.
///
/// Phase 1 limitation: does not handle nested condition/loop branch offsets.
/// Deep nesting may produce overlapping nodes. Future versions will use
/// tree layout or dagre/ELK integration.
pub fn auto_layout(nodes: &[CanonicalNode], config: &LayoutConfig) -> Vec<Position> {
    nodes
        .iter()
        .enumerate()
        .map(|(i, _)| Position {
            x: config.start_x,
            y: config.start_y + (i as f64) * config.y_gap,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn dummy_node(id: &str) -> CanonicalNode {
        CanonicalNode {
            id: id.into(),
            kind: NodeKind::Action,
            action: Some("Click".into()),
            position: Position { x: 0.0, y: 0.0 },
            data: json!({}),
            settings: None,
            runtime: None,
            selected: None,
        }
    }

    #[test]
    fn layout_linear() {
        let nodes = vec![dummy_node("1"), dummy_node("2"), dummy_node("3")];
        let config = LayoutConfig::default();
        let positions = auto_layout(&nodes, &config);

        assert_eq!(positions.len(), 3);
        assert_eq!(positions[0].x, 300.0);
        assert_eq!(positions[0].y, 100.0);
        assert_eq!(positions[1].y, 220.0);
        assert_eq!(positions[2].y, 340.0);
    }

    #[test]
    fn layout_empty() {
        let positions = auto_layout(&[], &LayoutConfig::default());
        assert!(positions.is_empty());
    }
}
