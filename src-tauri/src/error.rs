use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Database error: {0}")]
    Database(#[from] rusqlite::Error),

    #[error("Sidecar error: {0}")]
    Sidecar(String),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Validation failed")]
    Validation(Vec<crate::workflow_validator::Diagnostic>),

    #[error("Transform error: {0}")]
    Transform(String),
}

impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeMap;
        let (kind, message, diagnostics) = match self {
            AppError::Database(e) => ("database", e.to_string(), None),
            AppError::Sidecar(s) => ("sidecar", s.clone(), None),
            AppError::Json(e) => ("json", e.to_string(), None),
            AppError::Io(e) => ("io", e.to_string(), None),
            AppError::Validation(diags) => (
                "validation",
                format!("{} validation error(s)", diags.len()),
                Some(diags),
            ),
            AppError::Transform(s) => ("transform", s.clone(), None),
        };
        let entries = if diagnostics.is_some() { 4 } else { 3 };
        let mut map = serializer.serialize_map(Some(entries))?;
        map.serialize_entry("kind", kind)?;
        map.serialize_entry("message", &message)?;
        map.serialize_entry("display", &self.to_string())?;
        if let Some(diags) = diagnostics {
            map.serialize_entry("diagnostics", diags)?;
        }
        map.end()
    }
}

pub type AppResult<T> = Result<T, AppError>;
