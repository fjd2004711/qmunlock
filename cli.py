#!/usr/bin/env python3
"""命令行入口。

用法:
  python cli.py <file.mgg> [输出目录]        # 单首 → mp3
  python cli.py <目录> [输出目录]            # 批量 → mp3
  python cli.py --list <目录>                # 只列出可解的 .mgg
  python cli.py --creds                      # 检查本机凭据
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qmunlock import (convert_mgg, convert_directory,  # noqa: E402
                       get_credentials, CredentialsError)


def main():
    ap = argparse.ArgumentParser(description="QQ音乐 .mgg 离线解密 → mp3")
    ap.add_argument('target', nargs='?', default=None, help=".mgg/.mflac 文件 或 目录")
    ap.add_argument('outdir', nargs='?', default=None, help="输出目录（默认同目录）")
    ap.add_argument('--list', action='store_true', help="只列出可解文件")
    ap.add_argument('--creds', action='store_true', help="检查本机凭据后退出")
    ap.add_argument('--platform', default='20', help="20=macOS 27=Windows")
    args = ap.parse_args()

    if args.creds:
        try:
            c = get_credentials()
            # authst 是登录凭据，绝不能输出到终端、日志或 CI 记录中。
            print(f"✅ 凭据 OK  uin={c['uin']}  loginType={c['loginType']}  authst=已读取（已隐藏）")
        except CredentialsError as e:
            print(f"❌ {e}")
        return 0

    if not args.target:
        ap.print_usage()
        print("需要 <文件.mgg> 或 <目录>（或用 --creds / --list）")
        return 1

    if args.list:
        p = args.target
        if os.path.isfile(p):
            files = [p]
        else:
            files = [os.path.join(r, n) for r, _, ns in os.walk(p)
                     for n in sorted(ns) if n.lower().endswith(('.mgg', '.mflac'))]
        print(f"找到 {len(files)} 个加密文件:")
        for f in files:
            print("  ", f)
        return 0

    if os.path.isfile(args.target):
        out = convert_mgg(args.target, args.outdir, platform=args.platform)
        print(f"\n✅ {out} ({os.path.getsize(out)} 字节)")
    else:
        results = convert_directory(args.target, args.outdir, platform=args.platform)
        ok = [r for r in results if r['ok']]
        bad = [r for r in results if not r['ok']]
        for r in ok:
            print(f"  ✅ {r['output']}")
        for r in bad:
            print(f"  ❌ {r['input']}  → {r['error']}")
        print(f"\n完成: {len(ok)} 成功, {len(bad)} 失败")
    return 0


if __name__ == '__main__':
    sys.exit(main())
