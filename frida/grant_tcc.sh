#!/bin/bash
DB="/Library/Application Support/com.apple.TCC/TCC.db"
DIR="/Library/Application Support/com.apple.TCC"
echo "[1] dir writable test:"
if sudo touch "$DIR/.wtest" 2>/dev/null; then echo "    dir OK (writable)"; sudo rm -f "$DIR/.wtest"; else echo "    dir NOT writable!"; fi
echo "[2] try UPDATE with journal_mode=memory:"
sudo sqlite3 "$DB" "PRAGMA journal_mode=memory; BEGIN; UPDATE access SET auth_value=2, auth_reason=4 WHERE service='kTCCServiceDeveloperTool' AND client='com.apple.Terminal'; COMMIT;" 2>&1
echo "[3] verify:"
sqlite3 "$DB" "SELECT service, client, auth_value FROM access WHERE client='com.apple.Terminal' AND service IN ('kTCCServiceDeveloperTool','kTCCServiceDebug','kTCCServiceSystemPolicyAllFiles');"
echo "[4] restart tccd:"
sudo killall tccd 2>/dev/null || sudo pkill -x tccd 2>/dev/null || echo "    tccd kill (maybe already gone)"
echo "[+] DONE"
