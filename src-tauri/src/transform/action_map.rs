use std::collections::HashMap;
use std::sync::LazyLock;

/// PascalCase → snake_case mapping, loaded at compile time from shared/action-map.json
static ACTION_MAP: LazyLock<HashMap<String, String>> = LazyLock::new(|| {
    serde_json::from_str(include_str!("../../../shared/action-map.json"))
        .expect("invalid action-map.json")
});

/// snake_case → PascalCase reverse mapping
static REVERSE_MAP: LazyLock<HashMap<String, String>> = LazyLock::new(|| {
    ACTION_MAP.iter().map(|(k, v)| (v.clone(), k.clone())).collect()
});

/// Convert PascalCase action name to snake_case backend name.
/// Returns the input unchanged if no mapping exists.
pub fn to_backend(pascal: &str) -> String {
    ACTION_MAP
        .get(pascal)
        .cloned()
        .unwrap_or_else(|| pascal.to_string())
}

/// Convert snake_case backend name to PascalCase frontend name.
/// Returns the input unchanged if no mapping exists.
pub fn to_frontend(snake: &str) -> String {
    REVERSE_MAP
        .get(snake)
        .cloned()
        .unwrap_or_else(|| snake.to_string())
}

/// Check if a string looks like a known PascalCase action
pub fn is_pascal_case_action(name: &str) -> bool {
    ACTION_MAP.contains_key(name)
}

/// Check if a string looks like a known snake_case action
pub fn is_snake_case_action(name: &str) -> bool {
    REVERSE_MAP.contains_key(name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pascal_to_snake() {
        assert_eq!(to_backend("Navigate"), "open");
        assert_eq!(to_backend("Click"), "click");
        assert_eq!(to_backend("GetText"), "extract_text");
        assert_eq!(to_backend("HandleDialog"), "handle_dialog");
    }

    #[test]
    fn snake_to_pascal() {
        assert_eq!(to_frontend("open"), "Navigate");
        assert_eq!(to_frontend("click"), "Click");
        assert_eq!(to_frontend("extract_text"), "GetText");
    }

    #[test]
    fn unknown_passthrough() {
        assert_eq!(to_backend("UnknownAction"), "UnknownAction");
        assert_eq!(to_frontend("unknown_action"), "unknown_action");
    }

    #[test]
    fn detection_helpers() {
        assert!(is_pascal_case_action("Navigate"));
        assert!(!is_pascal_case_action("open"));
        assert!(is_snake_case_action("open"));
        assert!(!is_snake_case_action("Navigate"));
    }
}
