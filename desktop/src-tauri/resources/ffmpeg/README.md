# Bundled FFmpeg layout

The repository's `desktop/scripts/build-ffmpeg.sh` creates verified LGPL-only
FFmpeg executables at these paths:

- `resources/ffmpeg/macos-universal/ffmpeg`
- `resources/ffmpeg/windows-x64/ffmpeg.exe`

The application checks these bundled resources first, then falls back to
`ffmpeg` on the user's `PATH` for development. Do not replace them with a GPL
build.
