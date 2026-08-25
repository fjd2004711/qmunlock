use super::{Error, MusicExFooter, Result};
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

const MAGIC: &[u8] = b"musicex\0";
const MIN_FOOTER_SIZE: u64 = 192;

pub fn parse_file(path: &Path) -> Result<MusicExFooter> {
    let mut file = File::open(path)?;
    let length = file.metadata()?.len();
    if length < MIN_FOOTER_SIZE {
        return Err(Error::from("文件太小，不是有效的 musicex 文件"));
    }
    file.seek(SeekFrom::End(-16))?;
    let mut trailer = [0u8; 16];
    file.read_exact(&mut trailer)?;
    if &trailer[8..] != MAGIC {
        return Err(Error::from("文件尾部不是 musicex 格式"));
    }
    let footer_size = u32::from_le_bytes(trailer[..4].try_into().unwrap()) as u64;
    if footer_size < MIN_FOOTER_SIZE || footer_size > length {
        return Err(Error::from("musicex footer 长度非法"));
    }
    file.seek(SeekFrom::Start(length - footer_size))?;
    let mut footer = vec![0u8; footer_size as usize];
    file.read_exact(&mut footer)?;
    let song_mid = utf16_field(&footer, 0x0c, 60)?;
    let filename = utf16_field(&footer, 0x48, 68)?;
    if song_mid.is_empty() || filename.is_empty() {
        return Err(Error::from("musicex footer 缺少歌曲 MID 或资源文件名"));
    }
    if !filename.to_ascii_lowercase().ends_with(".mgg")
        && !filename.to_ascii_lowercase().ends_with(".mflac")
    {
        return Err(Error::from("musicex footer 的资源文件名扩展名非法"));
    }
    Ok(MusicExFooter {
        audio_length: length - footer_size,
        song_mid,
        filename,
    })
}

fn utf16_field(data: &[u8], start: usize, length: usize) -> Result<String> {
    let bytes = data
        .get(start..start + length)
        .ok_or("musicex footer 字段越界")?;
    let (chunks, remainder) = bytes.as_chunks::<2>();
    if !remainder.is_empty() {
        return Err(Error::from("musicex footer 的 UTF-16 字段长度非法"));
    }
    let words: Vec<u16> = chunks
        .iter()
        .map(|x| u16::from_le_bytes(*x))
        .take_while(|x| *x != 0)
        .collect();
    String::from_utf16(&words).map_err(|_| Error::from("musicex footer 的 UTF-16 字段非法"))
}
