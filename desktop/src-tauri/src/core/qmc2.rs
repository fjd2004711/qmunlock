use super::{Error, Result};
use base64::{engine::general_purpose::STANDARD, Engine as _};

const SIMPLE_KEY: [u8; 8] = [0x69, 0x56, 0x46, 0x38, 0x2b, 0x20, 0x15, 0x0b];
const V2_PREFIX: &[u8] = b"QQMusic EncV2,Key:";
const V2_KEY_1: &[u8; 16] = b"386ZJY!@#*$%^&)(";
const V2_KEY_2: &[u8; 16] = b"**#!(#$%&^a1cZ,T";

pub fn derive_key(encoded: &str) -> Result<Vec<u8>> {
    let mut decoded = STANDARD
        .decode(encoded.trim())
        .map_err(|_| Error::from("ekey 不是有效的 base64"))?;
    if decoded.starts_with(V2_PREFIX) {
        decoded = tencent_tea_decrypt(&decoded[V2_PREFIX.len()..], V2_KEY_1)?;
        decoded = tencent_tea_decrypt(&decoded, V2_KEY_2)?;
        let inner =
            std::str::from_utf8(&decoded).map_err(|_| Error::from("EncV2 ekey 不是 UTF-8"))?;
        decoded = STANDARD
            .decode(inner.trim())
            .map_err(|_| Error::from("EncV2 内层 ekey 不是 base64"))?;
    }
    if decoded.len() < 8 {
        return Err(Error::from("ekey 过短"));
    }
    if decoded.len() == 8 {
        return Ok(decoded);
    }
    let mut tea_key = [0u8; 16];
    for i in 0..8 {
        tea_key[i * 2] = SIMPLE_KEY[i];
        tea_key[i * 2 + 1] = decoded[i];
    }
    // music.vkey.GetEVkey may return an EncV1 key or a raw decoded key,
    // depending on the client/version.  EncV1 has a TC-TEA encrypted body;
    // a raw key must be used as-is instead of rejecting it.
    match tencent_tea_decrypt(&decoded[8..], &tea_key) {
        Ok(body) => {
            let mut key = decoded[..8].to_vec();
            key.extend(body);
            Ok(key)
        }
        Err(_) => Ok(decoded),
    }
}

pub fn decrypt_chunk(data: &mut [u8], key: &[u8], offset: u64) {
    if key.len() > 300 {
        Rc4::new(key).decrypt(data, offset);
    } else {
        map_decrypt(data, key, offset);
    }
}

pub fn detect_format(data: &[u8]) -> &'static str {
    if data.starts_with(b"OggS") {
        "ogg"
    } else if data.starts_with(b"fLaC") {
        "flac"
    } else if data.starts_with(b"ID3") || data.first() == Some(&0xff) {
        "mp3"
    } else {
        "bin"
    }
}

fn map_decrypt(data: &mut [u8], key: &[u8], offset: u64) {
    for (i, byte) in data.iter_mut().enumerate() {
        let off = (offset + i as u64) % 0x7fff;
        let index = ((off * off + 71214) % key.len() as u64) as usize;
        let shift = ((index as u32 & 7) + 4) & 7;
        let value = key[index].rotate_left(shift);
        *byte ^= value;
    }
}

struct Rc4<'a> {
    key: &'a [u8],
    box_: Vec<u8>,
    hash: u32,
}
impl<'a> Rc4<'a> {
    const SEGMENT: u64 = 5120;
    fn new(key: &'a [u8]) -> Self {
        let n = key.len();
        let mut box_: Vec<u8> = (0..n as u16).map(|x| x as u8).collect();
        let mut j = 0usize;
        for i in 0..n {
            j = (j + box_[i] as usize + key[i % n] as usize) % n;
            box_.swap(i, j);
        }
        let mut hash = 1u32;
        for value in key {
            if *value == 0 {
                continue;
            }
            let next = hash.wrapping_mul(*value as u32);
            if next == 0 || next <= hash {
                break;
            }
            hash = next;
        }
        Self { key, box_, hash }
    }
    fn skip(&self, id: u64) -> usize {
        let seed = self.key[id as usize % self.key.len()];
        if seed == 0 {
            0
        } else {
            ((self.hash as f64 / ((id + 1) as f64 * seed as f64)) * 100.0) as usize % self.key.len()
        }
    }
    fn decrypt(&self, data: &mut [u8], offset: u64) {
        let mut done = 0usize;
        while done < data.len() {
            let at = offset + done as u64;
            if at < 128 {
                let count = (128 - at).min((data.len() - done) as u64) as usize;
                for i in 0..count {
                    data[done + i] ^= self.key[self.skip(at + i as u64)];
                }
                done += count;
                continue;
            }
            let block_end = ((at / Self::SEGMENT) + 1) * Self::SEGMENT;
            let count = (block_end - at).min((data.len() - done) as u64) as usize;
            self.crypt_segment(&mut data[done..done + count], at);
            done += count;
        }
    }
    fn crypt_segment(&self, data: &mut [u8], offset: u64) {
        let n = self.key.len();
        let mut box_ = self.box_.clone();
        let mut j = 0usize;
        let mut k = 0usize;
        let skip = (offset % Self::SEGMENT) as usize + self.skip(offset / Self::SEGMENT);
        for step in 0..skip + data.len() {
            j = (j + 1) % n;
            k = (k + box_[j] as usize) % n;
            box_.swap(j, k);
            if step >= skip {
                data[step - skip] ^= box_[(box_[j] as usize + box_[k] as usize) % n];
            }
        }
    }
}

fn tencent_tea_decrypt(data: &[u8], key: &[u8; 16]) -> Result<Vec<u8>> {
    if data.len() < 16 || !data.len().is_multiple_of(8) {
        return Err(Error::from("TC-TEA 密文长度非法"));
    }
    let mut previous = [0u8; 8];
    let mut current = [0u8; 8];
    current.copy_from_slice(&data[..8]);
    let mut block = decrypt_block(current, key);
    let padding = (block[0] & 7) as usize;
    let out_len = data
        .len()
        .checked_sub(10 + padding)
        .ok_or("TC-TEA 填充非法")?;
    let mut output = Vec::with_capacity(out_len);
    let mut input = 8usize;
    let mut pos = 1 + padding;
    // Tencent-TEA prefixes the payload with two salt bytes after padding.
    for _ in 0..2 {
        if pos == 8 {
            if input + 8 > data.len() {
                return Err(Error::from("TC-TEA 数据截断"));
            }
            previous = current;
            current.copy_from_slice(&data[input..input + 8]);
            for i in 0..8 {
                block[i] ^= current[i];
            }
            block = decrypt_block(block, key);
            input += 8;
            pos = 0;
        }
        pos += 1;
    }
    while output.len() < out_len {
        if pos == 8 {
            if input + 8 > data.len() {
                return Err(Error::from("TC-TEA 数据截断"));
            }
            previous = current;
            current.copy_from_slice(&data[input..input + 8]);
            for i in 0..8 {
                block[i] ^= current[i];
            }
            block = decrypt_block(block, key);
            input += 8;
            pos = 0;
        }
        output.push(block[pos] ^ previous[pos]);
        pos += 1;
    }
    Ok(output)
}

fn decrypt_block(mut block: [u8; 8], key: &[u8; 16]) -> [u8; 8] {
    let mut v0 = u32::from_be_bytes(block[..4].try_into().unwrap());
    let mut v1 = u32::from_be_bytes(block[4..].try_into().unwrap());
    let k: [u32; 4] = [
        u32::from_be_bytes(key[..4].try_into().unwrap()),
        u32::from_be_bytes(key[4..8].try_into().unwrap()),
        u32::from_be_bytes(key[8..12].try_into().unwrap()),
        u32::from_be_bytes(key[12..].try_into().unwrap()),
    ];
    let mut sum = 0xe3779b90u32;
    for _ in 0..16 {
        v1 = v1.wrapping_sub(
            ((v0 << 4).wrapping_add(k[2]))
                ^ (v0.wrapping_add(sum))
                ^ ((v0 >> 5).wrapping_add(k[3])),
        );
        v0 = v0.wrapping_sub(
            ((v1 << 4).wrapping_add(k[0]))
                ^ (v1.wrapping_add(sum))
                ^ ((v1 >> 5).wrapping_add(k[1])),
        );
        sum = sum.wrapping_sub(0x9e3779b9);
    }
    block[..4].copy_from_slice(&v0.to_be_bytes());
    block[4..].copy_from_slice(&v1.to_be_bytes());
    block
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn map_is_symmetric() {
        let key = b"valid test key";
        let mut value = b"known bytes".to_vec();
        let original = value.clone();
        map_decrypt(&mut value, key, 0);
        map_decrypt(&mut value, key, 0);
        assert_eq!(value, original);
    }
    #[test]
    fn detects_headers() {
        assert_eq!(detect_format(b"OggS"), "ogg");
        assert_eq!(detect_format(b"fLaC"), "flac");
    }

    #[test]
    fn accepts_raw_api_key_when_tea_body_is_not_encv1() {
        let raw = b"raw-api-key!";
        let encoded = STANDARD.encode(raw);
        assert_eq!(derive_key(&encoded).unwrap(), raw);
    }

    #[test]
    fn rc4_is_symmetric_across_segments() {
        let key: Vec<u8> = (0..512).map(|i| ((i * 37 + 11) & 0xff) as u8).collect();
        let original: Vec<u8> = (0..12_000).map(|i| (i & 0xff) as u8).collect();
        let mut encrypted = original.clone();
        let rc4 = Rc4::new(&key);
        rc4.decrypt(&mut encrypted, 0);
        rc4.decrypt(&mut encrypted, 0);
        assert_eq!(encrypted, original);
    }
}
