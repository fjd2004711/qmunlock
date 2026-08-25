#!/usr/bin/env bash
set -euo pipefail

target="${1:?usage: sign-and-package-macos.sh <rust-target>}"

case "$target" in
  aarch64-apple-darwin) arch="aarch64" ;;
  x86_64-apple-darwin) arch="x64" ;;
  *)
    echo "Unsupported macOS target: $target" >&2
    exit 2
    ;;
esac

bundle_dir="src-tauri/target/$target/release/bundle"
app_path="$(find "$bundle_dir/macos" -maxdepth 1 -type d -name '*.app' -print -quit)"
if [[ -z "$app_path" ]]; then
  echo "macOS app bundle was not generated for $target" >&2
  exit 1
fi

app_name="$(basename "$app_path" .app)"
version="$(node -p 'require("./package.json").version')"
dmg_dir="$bundle_dir/dmg"
dmg_path="$dmg_dir/${app_name}_${version}_${arch}.dmg"

echo "Ad-hoc signing $app_path"
codesign --force --deep --sign - --timestamp=none "$app_path"

echo "Verifying app bundle signature"
codesign --verify --deep --strict --verbose=4 "$app_path"

echo "Verifying nested frameworks, helpers, dylibs, and executables"
for nested_root in \
  "$app_path/Contents/MacOS" \
  "$app_path/Contents/Frameworks" \
  "$app_path/Contents/Helpers" \
  "$app_path/Contents/PlugIns" \
  "$app_path/Contents/XPCServices"; do
  [[ -d "$nested_root" ]] || continue
  while IFS= read -r -d '' nested_code; do
    if [[ -f "$nested_code" ]]; then
      if ! file -b "$nested_code" | grep -q 'Mach-O'; then
        continue
      fi
    fi
    codesign --verify --deep --strict --verbose=4 "$nested_code"
  done < <(
    find "$nested_root" \
      \( -type d \( -name '*.app' -o -name '*.framework' \) -o \
         -type f \( -name '*.dylib' -o -perm -111 \) \) \
      -print0
  )
done

mkdir -p "$dmg_dir"
echo "Creating DMG from the verified app bundle"
hdiutil create \
  -volname "$app_name" \
  -srcfolder "$app_path" \
  -ov \
  -format UDZO \
  "$dmg_path"
hdiutil verify "$dmg_path"

mount_dir="$(mktemp -d -t qmunlock-dmg-verify)"
cleanup() {
  hdiutil detach "$mount_dir" -force >/dev/null 2>&1 || true
  rmdir "$mount_dir" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Verifying the app after DMG creation"
hdiutil attach -readonly -nobrowse -mountpoint "$mount_dir" "$dmg_path" >/dev/null
codesign --verify --deep --strict --verbose=4 "$mount_dir/$app_name.app"

echo "Created and verified $dmg_path"
