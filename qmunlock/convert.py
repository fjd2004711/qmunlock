"""音频格式转换（依赖 ffmpeg / afconvert）。

优先级：ffmpeg（出 mp3 192k）→ afconvert（macOS 自带，出 m4a）。
ffmpeg 未装时自动回退到 afconvert。
"""
import os
import shutil
import subprocess


def has_ffmpeg():
    return shutil.which('ffmpeg') is not None


def to_mp3(input_path, output_dir=None, prefer="mp3"):
    """把 ogg/flac 转成 mp3（或 m4a 回退）。返回输出文件路径。

    输出文件名 = 输入去扩展名 + .mp3/.m4a，写到 output_dir（默认同目录）。
    转不出任何 >1KB 的音频时抛 ConvertError。
    """
    outdir = output_dir or os.path.dirname(input_path) or '.'
    base = os.path.splitext(os.path.basename(input_path))[0]
    os.makedirs(outdir, exist_ok=True)

    if has_ffmpeg():
        for ext in (".mp3", ".ogg", ".m4a"):
            out = os.path.join(outdir, base + ext)
            r = subprocess.run(["ffmpeg", "-y", "-i", input_path, out],
                               capture_output=True)
            if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
                return out
    # 回退：macOS afconvert → m4a
    out = os.path.join(outdir, base + ".m4a")
    r = subprocess.run(["afconvert", "-f", "m4af", "-d", "aacf", "-b", "192000",
                        input_path, out], capture_output=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
        return out
    raise ConvertError(f"转码失败（ffmpeg/afconvert 都没出有效音频）: {input_path}")


class ConvertError(Exception):
    pass
