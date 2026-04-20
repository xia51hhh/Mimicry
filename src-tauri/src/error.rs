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
}

impl serde::Serialize for AppError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        use serde::ser::SerializeMap;
        let mut map = serializer.serialize_map(Some(3))?;
        let (kind, message) = match self {
            AppError::Database(e) => ("database", e.to_string()),
            AppError::Sidecar(s) => ("sidecar", s.clone()),
            AppError::Json(e) => ("json", e.to_string()),
            AppError::Io(e) => ("io", e.to_string()),
        };
        map.serialize_entry("kind", kind)?;
        map.serialize_entry("message", &message)?;
        map.serialize_entry("display", &self.to_string())?;
        map.end()
    }
}

pub type AppResult<T> = Result<T, AppError>;
