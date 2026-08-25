# Bundled FFmpeg

The release resources contain a minimal statically linked FFmpeg `8.0.1`
build. It is configured with `--disable-gpl --disable-nonfree` and only links
the LGPL LAME 3.100 encoder. Only the `ffmpeg` command, file protocol,
OGG/FLAC/MP3 demuxers and decoders, `libmp3lame`, and audio resample filters
are enabled.

Source archive: <https://ffmpeg.org/releases/ffmpeg-8.0.1.tar.xz>

SHA-256:

`05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41`

LAME source archive: <https://downloads.sourceforge.net/lame/lame/3.100/lame-3.100.tar.gz>

LAME SHA-256:

`ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e`

The exact configure and build steps are in `desktop/scripts/build-ffmpeg.sh`.
