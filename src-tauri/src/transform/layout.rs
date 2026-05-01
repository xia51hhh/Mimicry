use super::types::*;

/// Layout configuration
pub struct LayoutConfig {
    pub start_x: f64,
    pub start_y: f64,
    pub y_gap: f64,
    pub branch_offset_x: f64,
}

impl Default for LayoutConfig {
    fn default() -> Self {
        Self {
            start_x: 300.0,
            start_y: 100.0,
            y_gap: 120.0,
            branch_offset_x: 300.0,
        }
    }
}

/// Edge definition with optional source handle (for condition/loop branching)
#[derive(Debug, Clone)]
pub struct EdgeDef {
    pub source: String,
    pub target: String,
    pub source_handle: Option<String>,
}

/// Generate positions for a flat list of canonical nodes using simple
/// top-down linear layout.
///
/// For workflows without branching, nodes are stacked vertically.
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

/// Layout engine that understands branching (condition/loop).
///
/// Walks the node graph using edges to discover branch structure,
/// then assigns positions with horizontal offsets for branches.
pub struct BranchAwareLayout {
    config: LayoutConfig,
    positions: std::collections::HashMap<String, Position>,
}

impl BranchAwareLayout {
    pub fn new(config: LayoutConfig) -> Self {
        Self {
            config,
            positions: std::collections::HashMap::new(),
        }
    }

    /// Compute positions for all nodes given the edge definitions.
    /// Returns positions in the same order as the input nodes.
    pub fn compute(
        &mut self,
        nodes: &[CanonicalNode],
        edges: &[EdgeDef],
    ) -> Vec<Position> {
        if nodes.is_empty() {
            return vec![];
        }

        // Build adjacency: source_id → Vec<(target_id, source_handle)>
        let mut adj: std::collections::HashMap<&str, Vec<(&str, Option<&str>)>> =
            std::collections::HashMap::new();
        let mut has_incoming: std::collections::HashSet<&str> =
            std::collections::HashSet::new();

        for e in edges {
            adj.entry(e.source.as_str())
                .or_default()
                .push((e.target.as_str(), e.source_handle.as_deref()));
            has_incoming.insert(e.target.as_str());
        }

        // Find root nodes (no incoming edges)
        let roots: Vec<&str> = nodes
            .iter()
            .filter(|n| !has_incoming.contains(n.id.as_str()))
            .map(|n| n.id.as_str())
            .collect();

        // Node kind lookup
        let kind_map: std::collections::HashMap<&str, &NodeKind> = nodes
            .iter()
            .map(|n| (n.id.as_str(), &n.kind))
            .collect();

        let mut cursor_y = self.config.start_y;

        if roots.is_empty() {
            // Fallback: linear layout
            for node in nodes {
                self.positions.insert(
                    node.id.clone(),
                    Position {
                        x: self.config.start_x,
                        y: cursor_y,
                    },
                );
                cursor_y += self.config.y_gap;
            }
        } else {
            // Walk from each root
            for root in &roots {
                self.layout_chain(
                    root,
                    self.config.start_x,
                    &mut cursor_y,
                    &adj,
                    &kind_map,
                );
            }
        }

        // Return positions in node order
        nodes
            .iter()
            .map(|n| {
                self.positions
                    .get(&n.id)
                    .cloned()
                    .unwrap_or(Position {
                        x: self.config.start_x,
                        y: 0.0,
                    })
            })
            .collect()
    }

    fn layout_chain(
        &mut self,
        node_id: &str,
        x: f64,
        y: &mut f64,
        adj: &std::collections::HashMap<&str, Vec<(&str, Option<&str>)>>,
        kind_map: &std::collections::HashMap<&str, &NodeKind>,
    ) {
        if self.positions.contains_key(node_id) {
            return;
        }

        let current_y = *y;
        self.positions.insert(
            node_id.to_string(),
            Position { x, y: current_y },
        );
        *y += self.config.y_gap;

        let children = match adj.get(node_id) {
            Some(c) => c.clone(),
            None => return,
        };

        let is_branching = kind_map
            .get(node_id)
            .is_some_and(|k| matches!(k, NodeKind::Condition | NodeKind::Loop));

        let has_handled_children = children.iter().any(|(_, h)| h.is_some());

        if is_branching && has_handled_children {
            // Group children by handle
            let mut true_targets = vec![];
            let mut false_targets = vec![];
            let mut body_targets = vec![];
            let mut done_targets = vec![];
            let mut plain_targets = vec![];

            for (target, handle) in &children {
                match handle.as_deref() {
                    Some("true") | Some("body") => {
                        if handle.as_deref() == Some("true") {
                            true_targets.push(*target);
                        } else {
                            body_targets.push(*target);
                        }
                    }
                    Some("false") | Some("done") => {
                        if handle.as_deref() == Some("false") {
                            false_targets.push(*target);
                        } else {
                            done_targets.push(*target);
                        }
                    }
                    _ => plain_targets.push(*target),
                }
            }

            let left_targets = if !true_targets.is_empty() {
                true_targets
            } else {
                body_targets
            };
            let right_targets = if !false_targets.is_empty() {
                false_targets
            } else {
                done_targets
            };

            let branch_y_start = *y;
            let offset = self.config.branch_offset_x;

            // Left branch (true / body)
            let mut left_y = branch_y_start;
            for target in &left_targets {
                self.layout_chain(target, x - offset, &mut left_y, adj, kind_map);
            }

            // Right branch (false / done)
            let mut right_y = branch_y_start;
            for target in &right_targets {
                self.layout_chain(target, x + offset, &mut right_y, adj, kind_map);
            }

            // Advance y past the longer branch
            *y = left_y.max(right_y);

            // Plain targets (no handle) continue linearly
            for target in &plain_targets {
                self.layout_chain(target, x, y, adj, kind_map);
            }
        } else {
            // Sequential: all children continue linearly
            for (target, _) in &children {
                self.layout_chain(target, x, y, adj, kind_map);
            }
        }
    }
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

    fn cond_node(id: &str) -> CanonicalNode {
        CanonicalNode {
            id: id.into(),
            kind: NodeKind::Condition,
            action: None,
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

    #[test]
    fn branch_layout_condition() {
        // Condition → true: A, false: B → then C
        let nodes = vec![
            cond_node("cond"),
            dummy_node("a"),
            dummy_node("b"),
            dummy_node("c"),
        ];
        let edges = vec![
            EdgeDef {
                source: "cond".into(),
                target: "a".into(),
                source_handle: Some("true".into()),
            },
            EdgeDef {
                source: "cond".into(),
                target: "b".into(),
                source_handle: Some("false".into()),
            },
            EdgeDef {
                source: "a".into(),
                target: "c".into(),
                source_handle: None,
            },
        ];

        let config = LayoutConfig::default();
        let mut layout = BranchAwareLayout::new(config);
        let positions = layout.compute(&nodes, &edges);

        assert_eq!(positions.len(), 4);
        // Condition at center
        assert_eq!(positions[0].x, 300.0);
        // True branch (A) left offset
        assert_eq!(positions[1].x, 0.0); // 300 - 300
        // False branch (B) right offset
        assert_eq!(positions[2].x, 600.0); // 300 + 300
        // After merge: C at center
        assert_eq!(positions[3].x, 0.0); // continues from left chain
    }

    #[test]
    fn branch_layout_linear_fallback() {
        let nodes = vec![dummy_node("1"), dummy_node("2")];
        let edges = vec![EdgeDef {
            source: "1".into(),
            target: "2".into(),
            source_handle: None,
        }];

        let config = LayoutConfig::default();
        let mut layout = BranchAwareLayout::new(config);
        let positions = layout.compute(&nodes, &edges);

        assert_eq!(positions.len(), 2);
        assert_eq!(positions[0].x, 300.0);
        assert_eq!(positions[1].x, 300.0);
        assert!(positions[1].y > positions[0].y);
    }
}
