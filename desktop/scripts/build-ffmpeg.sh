#!/usr/bin/env bash
set -euo pipefail

# Build a small, statically linked LGPL-only FFmpeg for the two release
# targets. The source archive and digest are pinned for reproducibility.
FFMPEG_VERSION="8.0.1"
FFMPEG_SHA256="05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41"
LAME_VERSION="3.100"
LAME_SHA256="ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESOURCE_DIR="$ROOT_DIR/src-tauri/resources/ffmpeg"
BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/qmunlock-ffmpeg.XXXXXX")"
SOURCE_ARCHIVE="$BUILD_ROOT/ffmpeg-${FFMPEG_VERSION}.tar.xz"
LAME_ARCHIVE="$BUILD_ROOT/lame-${LAME_VERSION}.tar.gz"

cleanup() {
  if [[ "${KEEP_BUILD:-0}" == "1" ]]; then
    printf 'Keeping FFmpeg build directory: %s\n' "$BUILD_ROOT" >&2
  else
    rm -rf "$BUILD_ROOT"
  fi
}
trap cleanup EXIT

curl --fail --location --silent --show-error \
  "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" \
  --output "$SOURCE_ARCHIVE"
actual_sha256="$(shasum -a 256 "$SOURCE_ARCHIVE" | awk '{print $1}')"
if [[ "$actual_sha256" != "$FFMPEG_SHA256" ]]; then
  printf 'FFmpeg source digest mismatch: %s\n' "$actual_sha256" >&2
  exit 1
fi

tar -xf "$SOURCE_ARCHIVE" -C "$BUILD_ROOT"
SOURCE_DIR="$BUILD_ROOT/ffmpeg-${FFMPEG_VERSION}"

curl --fail --location --silent --show-error \
  "https://downloads.sourceforge.net/lame/lame/${LAME_VERSION}/lame-${LAME_VERSION}.tar.gz" \
  --output "$LAME_ARCHIVE"
actual_lame_sha256="$(shasum -a 256 "$LAME_ARCHIVE" | awk '{print $1}')"
if [[ "$actual_lame_sha256" != "$LAME_SHA256" ]]; then
  printf 'LAME source digest mismatch: %s\n' "$actual_lame_sha256" >&2
  exit 1
fi
tar -xf "$LAME_ARCHIVE" -C "$BUILD_ROOT"
LAME_SOURCE_DIR="$BUILD_ROOT/lame-${LAME_VERSION}"

common_configure=(
  --disable-debug
  --disable-doc
  --disable-ffplay
  --disable-ffprobe
  --disable-network
  --disable-autodetect
  --disable-everything
  --disable-gpl
  --disable-nonfree
  --disable-shared
  --enable-static
  --enable-small
  --enable-ffmpeg
  --enable-avcodec
  --enable-avformat
  --enable-avfilter
  --enable-swresample
  --enable-libmp3lame
  --enable-protocol=file
  --enable-demuxer=ogg,flac,mp3,mov
  --enable-muxer=mp3
  --enable-decoder=flac,vorbis,mp3,aac,alac,ac3,eac3
  --enable-encoder=libmp3lame
  --enable-parser=flac,vorbis,mpegaudio,aac,ac3
  --enable-filter=aresample,anull
)

build_lame() {
  local target="$1"
  local prefix="$2"
  shift 2
  local build_dir="$BUILD_ROOT/lame-build-$target"

  rm -rf "$build_dir"
  cp -R "$LAME_SOURCE_DIR" "$build_dir"
  pushd "$build_dir" >/dev/null
  local cc=clang
  local cflags=
  local ldflags=
  case "$target" in
    macos-arm64)
      cflags='-mmacosx-version-min=11.0'
      ldflags='-mmacosx-version-min=11.0'
      ;;
    macos-x86_64)
      cc='clang -arch x86_64'
      cflags='-arch x86_64 -mmacosx-version-min=11.0'
      ldflags='-arch x86_64 -mmacosx-version-min=11.0'
      ;;
    windows-x64)
      cc=x86_64-w64-mingw32-gcc
      ldflags='-static'
      ;;
  esac
  CC="$cc" CFLAGS="$cflags" LDFLAGS="$ldflags" ./configure \
    --prefix="$prefix" \
    --disable-frontend \
    --disable-shared \
    --enable-static \
    "$@"
  make -j"${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)}"
  make install
  popd >/dev/null
}

build_target() {
  local target="$1"
  local output="$2"
  local lame_prefix="$3"
  shift 3
  local build_dir="$BUILD_ROOT/build-$target"

  rm -rf "$build_dir"
  mkdir -p "$build_dir"
  pushd "$build_dir" >/dev/null
  printf 'Configuring FFmpeg target %s\n' "$target" >&2
  printf '  %q ' "$SOURCE_DIR/configure" "${common_configure[@]}" \
    "--prefix=$build_dir/prefix" "--extra-cflags=-I$lame_prefix/include" \
    "--extra-ldflags=-L$lame_prefix/lib" "$@" >&2
  printf '\n' >&2
  "$SOURCE_DIR/configure" \
    "${common_configure[@]}" \
    --prefix="$build_dir/prefix" \
    --extra-cflags="-I$lame_prefix/include" \
    --extra-ldflags="-L$lame_prefix/lib" \
    "$@"
  make -j"${JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)}"
  local binary=ffmpeg
  if [[ -f ffmpeg.exe ]]; then
    binary=ffmpeg.exe
  fi
  if [[ ! -f "$binary" ]]; then
    printf 'FFmpeg build did not produce an executable for %s\n' "$target" >&2
    exit 1
  fi
  cp "$binary" "$output"
  popd >/dev/null
}

verify_m4a_to_mp3_support() {
  local binary="$1"
  local decoder
  "$binary" -hide_banner -demuxers 2>&1 | grep -Eq '[[:space:]]mov[[:space:],]'
  for decoder in aac alac ac3 eac3; do
    "$binary" -hide_banner -decoders 2>&1 | grep -Eq "[[:space:]]$decoder[[:space:]]"
  done
}

mkdir -p "$RESOURCE_DIR/macos-universal" "$RESOURCE_DIR/windows-x64"
build_lame "macos-arm64" "$BUILD_ROOT/lame-prefix-arm64"
build_lame "macos-x86_64" "$BUILD_ROOT/lame-prefix-x86_64" \
  --host=x86_64-apple-darwin
build_target "macos-arm64" \
  "$BUILD_ROOT/ffmpeg-arm64" \
  "$BUILD_ROOT/lame-prefix-arm64" \
  --target-os=darwin --arch=arm64 --cc=clang \
  --extra-cflags=-mmacosx-version-min=11.0 \
  --extra-ldflags=-mmacosx-version-min=11.0
build_target "macos-x86_64" \
  "$BUILD_ROOT/ffmpeg-x86_64" \
  "$BUILD_ROOT/lame-prefix-x86_64" \
  --target-os=darwin --arch=x86_64 --enable-cross-compile --cc=clang \
  --disable-x86asm \
  '--extra-cflags=-arch x86_64 -mmacosx-version-min=11.0' \
  '--extra-ldflags=-arch x86_64 -mmacosx-version-min=11.0'
lipo -create "$BUILD_ROOT/ffmpeg-arm64" "$BUILD_ROOT/ffmpeg-x86_64" \
  -output "$RESOURCE_DIR/macos-universal/ffmpeg"
chmod 0755 "$RESOURCE_DIR/macos-universal/ffmpeg"
verify_m4a_to_mp3_support "$RESOURCE_DIR/macos-universal/ffmpeg"

if ! command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then
  printf 'x86_64-w64-mingw32-gcc is required for the Windows build\n' >&2
  exit 1
fi
build_lame "windows-x64" "$BUILD_ROOT/lame-prefix-windows" \
  --host=x86_64-w64-mingw32
build_target "windows-x64" \
  "$RESOURCE_DIR/windows-x64/ffmpeg.exe" \
  "$BUILD_ROOT/lame-prefix-windows" \
  --target-os=mingw32 --arch=x86_64 --enable-cross-compile \
  --cross-prefix=x86_64-w64-mingw32- --cc=x86_64-w64-mingw32-gcc \
  --enable-w32threads --disable-x86asm --extra-ldflags=-static
chmod 0755 "$RESOURCE_DIR/windows-x64/ffmpeg.exe"

cp "$SOURCE_DIR/COPYING.LGPLv2.1" "$RESOURCE_DIR/COPYING.LGPLv2.1"
cp "$LAME_SOURCE_DIR/COPYING" "$RESOURCE_DIR/COPYING.LAME"
printf 'Built FFmpeg %s from pinned official source.\n' "$FFMPEG_VERSION"
