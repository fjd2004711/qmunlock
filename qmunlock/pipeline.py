"""完整编排：.mgg → 解析 footer → 取 ekey → 解密 → 转 mp3。

这是给上层（app / cli）用的主入口：
    from qmunlock.pipeline import convert_mgg, convert_directory

    convert_mgg("刘欢-千万次的问.mgg", outdir="/tmp/out")      # 单首
    convert_directory("/path/to/iQmc", outdir="/tmp/out")      # 批量
"""
import os

from . import credentials, footer, ekey, convert, qmc2


class DecryptError(Exception):
    pass


def _ekey_cache():
    return {}


def convert_mgg(mgg_path, outdir=None, cred=None, platform="20", log=print):
    """解密单个 .mgg/.mflac，转成 mp3（或回退 m4a）。返回输出文件路径。

    参数：
      mgg_path   加密文件路径
      outdir     输出目录（默认同目录）
      cred       credentials.get_credentials() 结果（缺省则自动读 plist）
      platform   "20"=macOS / "27"=Windows
    """
    outdir = outdir or os.path.dirname(mgg_path) or '.'
    os.makedirs(outdir, exist_ok=True)
    if cred is None:
        cred = credentials.get_credentials()

    with open(mgg_path, 'rb') as f:
        data = f.read()

    # 1. footer → mid + filename
    info = footer.parse_footer(data)
    mid, fname = info['mid'], info['filename']

    # 2. API → ekey
    ekey_b64 = ekey.fetch_ekey_str(mid, fname, cred, platform=platform)

    # 3. 解密（只解 audio 部分）
    alen = footer.audio_length(data)
    plaintext, fmt = qmc2.decrypt_qmc2(data[:alen], ekey_b64)

    # 4. 落地 + 转 mp3
    base = os.path.splitext(os.path.basename(mgg_path))[0]
    ext = fmt if fmt in ('ogg', 'flac', 'mp3') else 'bin'
    mid_path = os.path.join(outdir, base + '.' + ext)
    with open(mid_path, 'wb') as f:
        f.write(plaintext)

    if fmt == 'mp3':
        return mid_path  # 本身就是 mp3，无需转
    return convert.to_mp3(mid_path, outdir)


def convert_directory(dir_path, outdir=None, cred=None, platform="20",
                      exts=(".mgg", ".mflac"), log=print):
    """批量解密目录下所有加密文件。

    返回 [{input, output, ok, error}] 列表。单首失败不中断整批。
    """
    cred = cred or credentials.get_credentials()
    results = []
    files = []
    if os.path.isfile(dir_path):
        files = [dir_path]
    else:
        for root, _, names in os.walk(dir_path):
            for n in sorted(names):
                if n.lower().endswith(exts):
                    files.append(os.path.join(root, n))
    for fp in files:
        try:
            out = convert_mgg(fp, outdir, cred=cred, platform=platform, log=log)
            results.append({'input': fp, 'output': out, 'ok': True})
        except Exception as e:
            results.append({'input': fp, 'output': None, 'ok': False, 'error': str(e)})
    return results


# 便捷别名
convert_file = convert_mgg
