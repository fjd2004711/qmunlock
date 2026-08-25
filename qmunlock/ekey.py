"""通过 QQ音乐 官方 API 获取 ekey（无需 hook）。

端点:  POST https://u.y.qq.com/cgi-bin/musicu.fcg
模块:  music.vkey.GetEVkey  (method: CgiGetEVkey)

关键点：
  - filename 必须带 .mgg/.mflac 扩展名，否则 ekey 为空
  - songtype 必须为 [1]（加密资源）
  - platform: "20" = macOS, "27" = Windows
  - 认证用 comm.authst（从 plist 取）
  - ekey 有效期 ~22h（expiration=80400）

返回: req_1.data.midurlinfo[0] = { ekey, vkey, purl, songmid, filename, result }
"""
import json
import urllib.request

API_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) QQMusic/19"


class EKeyError(Exception):
    pass


def _post(payload, timeout=20):
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'User-Agent': USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_ekey(mid, filename, uin, authst, login_type="3", platform="20"):
    """调 GetEVkey 取 ekey。返回 dict（含 ekey/vkey/purl）。失败抛 EKeyError。"""
    payload = {
        "comm": {
            "authst": authst,
            "ct": "19",
            "cv": "1859",
            "uin": uin,
            "tmeLoginType": login_type,
        },
        "req_1": {
            "module": "music.vkey.GetEVkey",
            "method": "CgiGetEVkey",
            "param": {
                "filename": [filename],
                "guid": "10000",
                "songmid": [mid],
                "songtype": [1],
                "uin": uin,
                "loginflag": 1,
                "platform": platform,
                "ctx": 1,
            },
        },
    }
    r = _post(payload)
    req1 = r.get('req_1', {})
    data = req1.get('data', {})
    midinfo = data.get('midurlinfo') or []
    if midinfo and midinfo[0].get('ekey'):
        return midinfo[0]
    # 诊断：retcode 405 / 空 ekey 多为 authst 过期或无权限
    raise EKeyError(
        f"API 未返回 ekey (retcode={data.get('retcode')} msg={data.get('msg')!r}): "
        + json.dumps(req1, ensure_ascii=False)[:300]
    )


def fetch_ekey_str(mid, filename, cred, platform="20"):
    """便捷版：传入 credentials.get_credentials() 的结果，直接返回 ekey 字符串。"""
    info = fetch_ekey(
        mid, filename,
        uin=cred['uin'], authst=cred['authst'],
        login_type=cred.get('loginType', '3'), platform=platform,
    )
    return info['ekey']
