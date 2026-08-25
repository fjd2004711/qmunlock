#!/bin/bash
# 把官方 QQMusic.app 重签成「可被 frida 附加」的副本（ad-hoc + get-task-allow）。
# 这样 frida attach 才能注入（原始 app 是 hardened runtime、无 get-task-allow，附加会失败）。
#
# 用法:
#   ./make_hookable_app.sh                       # 默认: /Applications/QQMusic.app → /tmp/qmunlock_hookable.app
#   ./make_hookable_app.sh <源app> [目标app]
#
# 之后:
#   open /tmp/qmunlock_hookable.app              # 用它登录 + 播放
#   frida -n QQMusic                             # 现在能附加了（见 capture.py）
set -euo pipefail
cd "$(dirname "$0")"

SRC="${1:-/Applications/QQMusic.app}"
DST="${2:-/tmp/qmunlock_hookable.app}"
ENT="$(pwd)/hook.entitlements"

[ -d "$SRC" ] || { echo "源 app 不存在: $SRC"; exit 1; }
[ -f "$ENT" ] || { echo "entitlements 不存在: $ENT"; exit 1; }

echo "[1/3] 复制 $SRC → $DST"
rm -rf "$DST"
cp -R "$SRC" "$DST"

echo "[2/3] 重签（ad-hoc + get-task-allow）"
# 先对每个内嵌 framework 重签，再签主 bundle（--deep 兜底）
find "$DST" -type d -name "*.framework" -print0 2>/dev/null | while IFS= read -r -d '' fw; do
  codesign --force --sign - --entitlements "$ENT" "$fw" 2>/dev/null || true
done
codesign --force --deep --sign - --entitlements "$ENT" "$DST"

echo "[3/3] 校验"
codesign -dv --entitlements - "$DST" 2>&1 | grep -i "get-task-allow" && echo "  ✅ get-task-allow 已加" || echo "  ⚠️ 没看到 get-task-allow，检查下"
echo ""
echo "完成: $DST"
echo "下一步:  open \"$DST\"  →  登录/播放  →  frida -n QQMusic"
