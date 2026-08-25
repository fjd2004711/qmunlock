use crate::core::{
    self, credentials, decrypt, ekey, DecryptOptions, DecryptResult, FileInfo, ProgressEvent,
};
use std::path::{Path, PathBuf};
use tauri::Emitter;

#[tauri::command]
pub fn check_credentials() -> core::CredentialStatus {
    credentials::status()
}

#[tauri::command]
pub fn get_file_info(path: String) -> FileInfo {
    let path = PathBuf::from(&path);
    match decrypt::info(&path) {
        Ok(footer) => FileInfo {
            path: path.display().to_string(),
            supported: true,
            format: Some("musicex/QMC2".into()),
            song_mid: Some(footer.song_mid),
            resource_filename: Some(footer.filename),
            error: None,
        },
        Err(error) => FileInfo {
            path: path.display().to_string(),
            supported: false,
            format: None,
            song_mid: None,
            resource_filename: None,
            error: Some(error.to_string()),
        },
    }
}

#[derive(Debug, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ScanResult {
    pub files: Vec<String>,
    pub infos: Vec<FileInfo>,
}

#[tauri::command]
pub fn scan_paths(app: tauri::AppHandle, paths: Vec<String>) -> ScanResult {
    let inputs = expand_paths(paths);
    let total = inputs.len().max(1) as u64;
    let mut infos = Vec::with_capacity(inputs.len());
    emit_progress(&app, "scan", "", 0, total, "正在扫描拖入的文件和文件夹");
    for (index, path) in inputs.iter().enumerate() {
        let info = match decrypt::info(path) {
            Ok(footer) => FileInfo {
                path: path.display().to_string(),
                supported: true,
                format: Some("musicex/QMC2".into()),
                song_mid: Some(footer.song_mid),
                resource_filename: Some(footer.filename),
                error: None,
            },
            Err(error) => FileInfo {
                path: path.display().to_string(),
                supported: false,
                format: None,
                song_mid: None,
                resource_filename: None,
                error: Some(error.to_string()),
            },
        };
        let current = (index + 1) as u64;
        emit_progress(
            &app,
            "parse",
            &info.path,
            current,
            total,
            &format!("正在解析 {}/{} 个文件", current, inputs.len()),
        );
        infos.push(info);
    }
    ScanResult {
        files: inputs
            .iter()
            .map(|path| path.display().to_string())
            .collect(),
        infos,
    }
}

#[tauri::command]
pub async fn decrypt_paths(
    app: tauri::AppHandle,
    paths: Vec<String>,
    output_dir: Option<String>,
    options: DecryptOptions,
) -> Vec<DecryptResult> {
    let inputs = expand_paths(paths);
    let output = output_dir.as_deref().map(Path::new);
    let credentials = if options
        .manual_ekey
        .as_deref()
        .unwrap_or_default()
        .trim()
        .is_empty()
    {
        credentials::load().ok()
    } else {
        None
    };
    let mut results = Vec::with_capacity(inputs.len());
    let total = inputs.len().max(1) as u64;
    for (index, input) in inputs.iter().enumerate() {
        let result = decrypt_one(
            &app,
            input,
            output,
            &options,
            credentials.as_ref(),
            (index + 1) as u64,
            total,
        )
        .await;
        results.push(result);
    }
    emit_progress(&app, "complete", "", total, total, "任务处理完成");
    results
}

async fn decrypt_one(
    app: &tauri::AppHandle,
    input: &Path,
    output_dir: Option<&Path>,
    options: &DecryptOptions,
    credentials: Option<&core::Credentials>,
    file_index: u64,
    file_total: u64,
) -> DecryptResult {
    let input_name = input.display().to_string();
    emit_progress(
        app,
        "parse",
        &input_name,
        file_index.saturating_sub(1),
        file_total,
        "正在读取 musicex footer",
    );
    let run = async {
        let footer = decrypt::info(input)?;
        emit_progress(app, "ekey", &input_name, 0, 1, "正在获取 ekey");
        let key = match options
            .manual_ekey
            .as_deref()
            .filter(|key| !key.trim().is_empty())
        {
            Some(key) => key.to_owned(),
            None => {
                let credentials =
                    credentials.ok_or("无法自动获取 ekey：请登录 QQ 音乐，或粘贴手动 ekey")?;
                ekey::fetch(&footer, credentials, credentials::api_platform()).await?
            }
        };
        let progress_app = app.clone();
        let progress_input = input_name.clone();
        decrypt::decrypt_file_with_progress(
            input,
            output_dir,
            &footer,
            &key,
            &options.output_mode,
            move |current, total, phase| {
                let message = if phase == "transcode" {
                    "正在转换为 MP3"
                } else {
                    "正在解密音频"
                };
                emit_progress(
                    &progress_app,
                    phase,
                    &progress_input,
                    current,
                    total,
                    message,
                );
            },
        )
    }
    .await;
    match run {
        Ok((output, format)) => DecryptResult {
            input: input_name,
            output: Some(output.display().to_string()),
            ok: true,
            format: Some(format),
            error: None,
        },
        Err(error) => DecryptResult {
            input: input_name,
            output: None,
            ok: false,
            format: None,
            error: Some(error.to_string()),
        },
    }
}

fn emit_progress(
    app: &tauri::AppHandle,
    phase: &str,
    input: &str,
    current: u64,
    total: u64,
    message: &str,
) {
    let percent = if total == 0 {
        0
    } else {
        ((current.min(total) as f64 / total as f64) * 100.0).round() as u8
    };
    let _ = app.emit(
        "decrypt-progress",
        ProgressEvent {
            phase: phase.into(),
            input: input.into(),
            current,
            total,
            percent,
            message: message.into(),
        },
    );
}

fn expand_paths(paths: Vec<String>) -> Vec<PathBuf> {
    let mut files = Vec::new();
    for path in paths.into_iter().map(PathBuf::from) {
        if path.is_file() {
            if core::supported_path(&path) {
                files.push(path);
            }
        } else if path.is_dir() {
            collect(&path, &mut files);
        }
    }
    files.sort();
    files.dedup();
    files
}

fn collect(path: &Path, files: &mut Vec<PathBuf>) {
    let Ok(entries) = std::fs::read_dir(path) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect(&path, files);
        } else if core::supported_path(&path) {
            files.push(path);
        }
    }
}
