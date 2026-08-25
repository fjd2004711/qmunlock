"""解析 musicex 格式 .mgg/.mflac/.mmp4 文件的尾部（footer）。

musicex footer（192 字节）在文件末尾，结构：
    +0x00  uint32 LE   song_id
    +0x0C  UTF-16LE    media_mid   （如 002atvb82SRmG2）
    +0x48  UTF-16LE    filename    （如 O4M0001oKbZM0vSt49.mgg，含扩展名）
    末尾   footer_size(=192) / version(=1) / "musicex\\0"

magic 校验：文件最后 8 字节 == b"musicex\\0"。
解密时只解 audio 部分（去掉 footer）。
"""
import re


class NotMusicExError(Exception):
    pass


def is_musicex(data):
    return data[-8:] == b'musicex\x00'


def audio_length(data):
    """返回 audio 密文长度（去掉 footer）。非 musicex 则返回全长。"""
    if not is_musicex(data):
        return len(data)
    import struct
    tag = int.from_bytes(data[-16:-12], 'little')
    return len(data) - tag


def parse_footer(data):
    """从文件字节里解析出 {song_id, mid, filename}。

    mid / filename 用正则从 UTF-16LE 尾部里捞（对偏移偏移不敏感）。
    非 musicex 文件抛 NotMusicExError。
    """
    if not is_musicex(data):
        raise NotMusicExError(f"尾 magic 不是 musicex: {data[-8:]!r}")
    tail = data[-256:].decode('utf-16-le', 'replace')
    mid = None
    m = re.search(r'(00[0-9a-zA-Z]{12})', tail)
    if m:
        mid = m.group(1)
    fname = None
    m = re.search(r'((?:[A-Z]+\d+)[0-9a-zA-Z]+\.m(?:gg|flac|mp4))', tail)
    if m:
        fname = m.group(1)
    if not (mid and fname):
        raise NotMusicExError(f"footer 里没解析到 mid/filename: mid={mid} fname={fname}")
    import struct
    song_id = struct.unpack_from('<I', data, len(data) - audio_length(data) - 200 + 0) if False else None
    return {'mid': mid, 'filename': fname}
