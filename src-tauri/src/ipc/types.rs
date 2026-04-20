use serde::{Deserialize, Serialize};

// --- Browser Launch ---
#[derive(Debug, Serialize)]
pub struct LaunchParams {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub headless: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<ProxyConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub profile: Option<ProfileConfig>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProxyConfig {
    pub server: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub password: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProfileConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub user_data_dir: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fingerprint: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub proxy: Option<ProxyConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub os_target: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct BrowserStatus {
    pub connected: bool,
    pub url: Option<String>,
    pub pages: u32,
}

// --- Workflow ---
#[derive(Debug, Deserialize)]
pub struct ExecutionResult {
    pub success: bool,
    pub running: bool,
    pub step: u32,
    pub total: u32,
    pub error: Option<String>,
    pub variables: Option<serde_json::Value>,
}
