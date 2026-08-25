pub mod credentials;
pub mod decrypt;
pub mod ekey;
pub mod footer;
pub mod qmc2;

use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CredentialStatus {
    pub available: bool,
    pub platform: String,
    pub account_hint: Option<String>,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FileInfo {
    pub path: String,
    pub supported: bool,
    pub format: Option<String>,
    pub song_mid: Option<String>,
    pub resource_filename: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DecryptResult {
    pub input: String,
    pub output: Option<String>,
    pub ok: bool,
    pub format: Option<String>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProgressEvent {
    pub phase: String,
    pub input: String,
    pub current: u64,
    pub total: u64,
    pub percent: u8,
    pub message: String,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct DecryptOptions {
    pub output_mode: OutputMode,
    pub manual_ekey: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OutputMode {
    Original,
    Mp3,
}

#[derive(Debug, Clone)]
pub struct Credentials {
    pub uin: String,
    pub authst: String,
    pub login_type: String,
}

#[derive(Debug, Clone)]
pub struct MusicExFooter {
    pub audio_length: u64,
    pub song_mid: String,
    pub filename: String,
}

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{0}")]
    Message(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
    #[error("network error: {0}")]
    Network(#[from] reqwest::Error),
}

impl From<&str> for Error {
    fn from(value: &str) -> Self {
        Self::Message(value.into())
    }
}
impl From<String> for Error {
    fn from(value: String) -> Self {
        Self::Message(value)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

pub fn supported_path(path: &Path) -> bool {
    matches!(
        path.extension()
            .and_then(|x| x.to_str())
            .map(|x| x.to_ascii_lowercase())
            .as_deref(),
        Some("mgg") | Some("mflac") | Some("mmp4")
    )
}
