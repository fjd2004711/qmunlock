"""qmunlock — QQ音乐 Mac .mgg (musicex/QMC2) 离线解密库。

一句话用法：
    from qmunlock import convert_mgg, convert_directory
    convert_mgg("刘欢-千万次的问.mgg", outdir="out/")          # → out/刘欢-千万次的问.mp3
    convert_directory("~/.../iQmc", outdir="out/")             # 批量

依赖：仅 Python 标准库 + (转码需) ffmpeg（或 macOS 自带 afconvert）。
凭据：本机 QQ音乐 登录过的 plist（uin + authst）。
"""
from .credentials import get_credentials, CredentialsError
from .footer import parse_footer, is_musicex, audio_length, NotMusicExError
from .ekey import fetch_ekey, fetch_ekey_str, EKeyError
from .qmc2 import decrypt_qmc2, derive_key, detect_fmt
from .convert import to_mp3, ConvertError
from .pipeline import convert_mgg, convert_directory, convert_file, DecryptError

__version__ = "0.1.0"

__all__ = [
    'get_credentials', 'CredentialsError',
    'parse_footer', 'is_musicex', 'audio_length', 'NotMusicExError',
    'fetch_ekey', 'fetch_ekey_str', 'EKeyError',
    'decrypt_qmc2', 'derive_key', 'detect_fmt',
    'to_mp3', 'ConvertError',
    'convert_mgg', 'convert_directory', 'convert_file', 'DecryptError',
    '__version__',
]
