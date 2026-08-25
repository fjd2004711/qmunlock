use super::{footer, qmc2, Error, MusicExFooter, OutputMode, Result};
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

const BUFFER_SIZE: usize = 256 * 1024;

pub fn decrypt_file_with_progress<F>(
    input: &Path,
    output_dir: Option<&Path>,
    footer: &MusicExFooter,
    ekey: &str,
    output_mode: &OutputMode,
    mut on_progress: F,
) -> Result<(PathBuf, String)>
where
    F: FnMut(u64, u64, &'static str),
{
    let key = qmc2::derive_key(ekey)?;
    let file = File::open(input)?;
    let mut reader = BufReader::new(file).take(footer.audio_length);
    let mut first = vec![0u8; BUFFER_SIZE.min(footer.audio_length as usize)];
    let first_len = reader.read(&mut first)?;
    if first_len == 0 {
        return Err(Error::from("加密音频部分为空"));
    }
    first.truncate(first_len);
    qmc2::decrypt_chunk(&mut first, &key, 0);
    let format = qmc2::detect_format(&first).to_string();
    if format == "bin" {
        return Err(Error::from("ekey 无效，或文件不是受支持的 QMC2 音频"));
    }
    let output_folder = output_dir.unwrap_or_else(|| input.parent().unwrap_or(Path::new(".")));
    fs::create_dir_all(output_folder)?;
    let stem = input
        .file_stem()
        .and_then(|value| value.to_str())
        .unwrap_or("decrypted");
    let raw_output = available_path(output_folder, stem, &format);
    let mut writer = BufWriter::new(File::create(&raw_output)?);
    writer.write_all(&first)?;
    let mut offset = first.len() as u64;
    on_progress(offset, footer.audio_length, "decrypt");
    let mut buffer = vec![0u8; BUFFER_SIZE];
    loop {
        let size = reader.read(&mut buffer)?;
        if size == 0 {
            break;
        }
        qmc2::decrypt_chunk(&mut buffer[..size], &key, offset);
        writer.write_all(&buffer[..size])?;
        offset += size as u64;
        on_progress(offset, footer.audio_length, "decrypt");
    }
    writer.flush()?;
    if matches!(output_mode, OutputMode::Mp3) && format != "mp3" {
        on_progress(0, 1, "transcode");
        let mp3_path = available_path(output_folder, stem, "mp3");
        convert_to_mp3(&raw_output, &mp3_path)?;
        on_progress(1, 1, "transcode");
        fs::remove_file(&raw_output)?;
        return Ok((mp3_path, "mp3".into()));
    }
    Ok((raw_output, format))
}

pub fn info(path: &Path) -> Result<MusicExFooter> {
    footer::parse_file(path)
}

fn available_path(directory: &Path, stem: &str, extension: &str) -> PathBuf {
    let base = directory.join(format!("{stem}.{extension}"));
    if !base.exists() {
        return base;
    }
    for index in 1..10_000 {
        let candidate = directory.join(format!("{stem} ({index}).{extension}"));
        if !candidate.exists() {
            return candidate;
        }
    }
    directory.join(format!("{stem}-decrypted.{extension}"))
}

fn convert_to_mp3(input: &Path, output: &Path) -> Result<()> {
    let result = Command::new(ffmpeg_path())
        .args(["-y", "-i"])
        .arg(input)
        .args(["-vn", "-codec:a", "libmp3lame", "-q:a", "2"])
        .arg(output)
        .output();
    match result {
        Ok(result)
            if result.status.success()
                && output
                    .metadata()
                    .map(|meta| meta.len() > 1024)
                    .unwrap_or(false) =>
        {
            Ok(())
        }
        Ok(result) => Err(Error::from(format!(
            "FFmpeg 转码失败：{}",
            String::from_utf8_lossy(&result.stderr)
                .lines()
                .last()
                .unwrap_or("未知错误")
        ))),
        Err(_) => Err(Error::from(
            "找不到 FFmpeg。发布包应包含 LGPL FFmpeg，开发环境请安装 ffmpeg 并加入 PATH",
        )),
    }
}

fn ffmpeg_path() -> PathBuf {
    let (folder, filename) = if cfg!(windows) {
        ("windows-x64", "ffmpeg.exe")
    } else {
        ("macos-universal", "ffmpeg")
    };
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let candidates = [
                parent.join("resources/ffmpeg").join(folder).join(filename),
                parent
                    .join("../Resources/resources/ffmpeg")
                    .join(folder)
                    .join(filename),
                parent
                    .join("../Resources/ffmpeg")
                    .join(folder)
                    .join(filename),
                parent.join(filename),
            ];
            for candidate in candidates {
                if candidate.exists() {
                    return candidate;
                }
            }
        }
    }
    PathBuf::from(filename)
}
