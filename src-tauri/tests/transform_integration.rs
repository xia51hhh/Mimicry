/// Integration tests for the transform module — full pipeline tests
use mimicry_lib::transform::*;

/// Simulate the exact workflow_execute path:
/// Frontend Canonical (PascalCase) → detect → canonical_to_backend → Backend (snake_case)
#[test]
fn execute_pipeline_bing_search() {
    let canonical_json = serde_json::json!({
        "name": "Bing搜索",
        "nodes": [
            {
                "id": "n1", "kind": "action", "action": "Navigate",
                "position": {"x": 300, "y": 100},
                "data": {"url": "https://www.bing.com"},
                "settings": {"note": "打开Bing"},
                "runtime": {"sessionId": "default"}
            },
            {
                "id": "n2", "kind": "action", "action": "Type",
                "position": {"x": 300, "y": 220},
                "data": {"selector": "textarea#sb_form_q", "value": "bilibili"}
            },
            {
                "id": "n3", "kind": "action", "action": "PressKey",
                "position": {"x": 300, "y": 340},
                "data": {"selector": "textarea#sb_form_q", "key": "Enter"}
            },
            {
                "id": "n4", "kind": "action", "action": "Click",
                "position": {"x": 300, "y": 460},
                "data": {"selector": "li.b_algo h2 a"}
            }
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"}
        ]
    });

    // Step 1: Detect format
    let fmt = detect_format(&canonical_json);
    assert_eq!(fmt, WorkflowFormat::Canonical);

    // Step 2: Deserialize to CanonicalWorkflow
    let canonical: CanonicalWorkflow = serde_json::from_value(canonical_json).unwrap();
    assert_eq!(canonical.nodes.len(), 4);

    // Step 3: Transform to Backend
    let backend = canonical_to_backend(&canonical, "default").unwrap();
    assert_eq!(backend.name, "Bing搜索");
    assert_eq!(backend.nodes.len(), 4);

    // Verify action name conversion
    assert_eq!(backend.nodes[0].action, "open");
    assert_eq!(backend.nodes[1].action, "type");
    assert_eq!(backend.nodes[2].action, "press_key");
    assert_eq!(backend.nodes[3].action, "click");

    // Verify session_id
    assert_eq!(backend.nodes[0].session_id, "default");
    assert_eq!(backend.nodes[1].session_id, "default"); // inherited default

    // Verify data preserved
    assert_eq!(backend.nodes[0].data["url"], "https://www.bing.com");
    assert_eq!(backend.nodes[1].data["selector"], "textarea#sb_form_q");

    // Verify JSON serialization matches Python expectations
    let json = serde_json::to_value(&backend).unwrap();
    let first_node = &json["nodes"][0];
    assert_eq!(first_node["kind"], "action");
    assert_eq!(first_node["type"], "action");
    assert_eq!(first_node["action"], "open");
    assert_eq!(first_node["session_id"], "default");
}

/// Test Compact → Canonical → Backend full pipeline
#[test]
fn import_pipeline_compact_to_backend() {
    let compact_json = serde_json::json!({
        "name": "LLM生成的工作流",
        "nodes": [
            {"action": "Navigate", "data": {"url": "https://example.com"}, "note": "打开网站"},
            {"action": "Click", "data": {"selector": "#login-btn"}},
            {"action": "Type", "data": {"selector": "#username", "value": "admin"}},
            {"action": "Type", "data": {"selector": "#password", "value": "pass123"}},
            {"action": "Click", "data": {"selector": "#submit"}}
        ]
    });

    // Step 1: Detect
    let fmt = detect_format(&compact_json);
    assert_eq!(fmt, WorkflowFormat::Compact);

    // Step 2: Compact → Canonical
    let compact: CompactWorkflow = serde_json::from_value(compact_json).unwrap();
    let canonical = compact_to_canonical(&compact).unwrap();

    assert_eq!(canonical.nodes.len(), 5);
    assert!(canonical.nodes[0].id.starts_with("node_"));
    assert!(canonical.nodes[0].position.y > 0.0);
    assert_eq!(canonical.nodes[0].action.as_deref(), Some("Navigate"));
    assert_eq!(
        canonical.nodes[0].settings.as_ref().unwrap().note.as_deref(),
        Some("打开网站")
    );
    // Should have 4 sequential edges
    assert_eq!(canonical.edges.len(), 4);

    // Step 3: Canonical → Backend
    let backend = canonical_to_backend(&canonical, "default").unwrap();
    assert_eq!(backend.nodes.len(), 5);
    assert_eq!(backend.nodes[0].action, "open");
    assert_eq!(backend.nodes[1].action, "click");
    assert_eq!(backend.nodes[2].action, "type");
}

/// Test Legacy → Canonical pipeline
#[test]
fn import_pipeline_legacy() {
    let legacy_json = serde_json::json!({
        "name": "旧格式工作流",
        "nodes": [
            {"type": "action", "action": "click", "selector": "#btn"},
            {"type": "action", "action": "Navigate", "url": "https://example.com"}
        ],
        "edges": []
    });

    let fmt = detect_format(&legacy_json);
    assert_eq!(fmt, WorkflowFormat::Legacy);

    let canonical = legacy_to_canonical(&legacy_json).unwrap();
    assert_eq!(canonical.nodes.len(), 2);
    assert_eq!(canonical.nodes[0].kind, NodeKind::Action);
    assert_eq!(canonical.nodes[0].action.as_deref(), Some("Click")); // snake→Pascal
    assert_eq!(canonical.nodes[1].action.as_deref(), Some("Navigate")); // already Pascal
    assert!(canonical.nodes[0].data.get("selector").is_some());
}

/// Test Recording format detection + conversion
#[test]
fn import_pipeline_recording() {
    let recording_json = serde_json::json!({
        "name": "Recording",
        "nodes": [
            {"kind": "action", "action": "click", "data": {"selector": "#btn"}},
            {"kind": "action", "action": "type", "data": {"selector": "#input", "value": "hello"}}
        ]
    });

    let fmt = detect_format(&recording_json);
    assert_eq!(fmt, WorkflowFormat::Recording);

    // Recording → Compact → Canonical full conversion chain
    let compact: CompactWorkflow = serde_json::from_value(recording_json).unwrap();
    let canonical = compact_to_canonical(&compact).unwrap();

    assert_eq!(canonical.nodes.len(), 2);
    assert_eq!(canonical.nodes[0].action.as_deref(), Some("Click")); // snake→Pascal
    assert_eq!(canonical.nodes[1].action.as_deref(), Some("Type"));
    assert!(canonical.nodes[0].data.get("selector").is_some());
    assert_eq!(canonical.edges.len(), 1); // auto-generated edge

    // Verify can further convert to Backend
    let backend = canonical_to_backend(&canonical, "default").unwrap();
    assert_eq!(backend.nodes[0].action, "click"); // Pascal→snake
    assert_eq!(backend.nodes[1].action, "type");
}

/// Test Canonical → Compact → Canonical roundtrip preserves execution semantics
#[test]
fn roundtrip_canonical_compact_semantics() {
    let original = serde_json::json!({
        "name": "Roundtrip Test",
        "nodes": [
            {
                "id": "n1", "kind": "action", "action": "Navigate",
                "position": {"x": 300, "y": 100},
                "data": {"url": "https://example.com"},
                "settings": {"note": "step 1", "onError": "stop"}
            },
            {
                "id": "n2", "kind": "action", "action": "Click",
                "position": {"x": 300, "y": 220},
                "data": {"selector": "#btn"}
            }
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}]
    });

    let canonical: CanonicalWorkflow = serde_json::from_value(original).unwrap();

    // Forward: Canonical → Compact
    let compact = canonical_to_compact(&canonical).unwrap();
    assert_eq!(compact.nodes.len(), 2);
    assert_eq!(compact.nodes[0].action, "Navigate");
    assert_eq!(compact.nodes[0].note.as_deref(), Some("step 1"));

    // Reverse: Compact → Canonical
    let restored = compact_to_canonical(&compact).unwrap();
    assert_eq!(restored.nodes.len(), 2);
    assert_eq!(restored.nodes[0].action.as_deref(), Some("Navigate"));
    assert_eq!(restored.nodes[0].data["url"], "https://example.com");
    assert_eq!(restored.nodes[1].action.as_deref(), Some("Click"));
    assert_eq!(restored.nodes[1].data["selector"], "#btn");

    // Both should produce identical backend output
    let backend1 = canonical_to_backend(&canonical, "default").unwrap();
    let backend2 = canonical_to_backend(&restored, "default").unwrap();
    assert_eq!(backend1.nodes.len(), backend2.nodes.len());
    for (a, b) in backend1.nodes.iter().zip(backend2.nodes.iter()) {
        assert_eq!(a.action, b.action);
        assert_eq!(a.data, b.data);
    }
}
