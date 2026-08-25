use super::{Credentials, Error, MusicExFooter, Result};
use serde_json::json;

const API_URL: &str = "https://u.y.qq.com/cgi-bin/musicu.fcg";

pub async fn fetch(
    footer: &MusicExFooter,
    credentials: &Credentials,
    platform: &str,
) -> Result<String> {
    let payload = json!({
        "comm": { "authst": credentials.authst, "ct": "19", "cv": "1859", "uin": credentials.uin, "tmeLoginType": credentials.login_type },
        "req_1": { "module": "music.vkey.GetEVkey", "method": "CgiGetEVkey", "param": { "filename": [footer.filename], "guid": "10000", "songmid": [footer.song_mid], "songtype": [1], "uin": credentials.uin, "loginflag": 1, "platform": platform, "ctx": 1 } }
    });
    let response: serde_json::Value = reqwest::Client::new()
        .post(API_URL)
        .header("User-Agent", "QQMusic/20 QMUnlock")
        .json(&payload)
        .send()
        .await?
        .error_for_status()?
        .json()
        .await?;
    let result = response
        .pointer("/req_1/data/midurlinfo/0/ekey")
        .and_then(|value| value.as_str())
        .filter(|value| !value.is_empty());
    result.map(str::to_owned).ok_or_else(|| {
        Error::from(format!(
            "API 未返回 ekey：{}",
            response
                .pointer("/req_1/code")
                .and_then(|v| v.as_i64())
                .unwrap_or(-1)
        ))
    })
}
