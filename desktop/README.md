# QM Unlock Desktop

跨平台图形界面，面向当前用户本地的 QQ 音乐 `musicex` 下载文件。

## 开发

```bash
cd desktop
npm install
npm run tauri dev
```

需要 Rust stable、Node.js 20+，以及对应平台的 Tauri 系统依赖。构建并放入两个平台
的 LGPL FFmpeg：

```bash
./scripts/build-ffmpeg.sh
```

该脚本在 macOS 构建机上生成 macOS universal 和 Windows x64 两个二进制；Windows
交叉编译需要先安装 `brew install mingw-w64`。源码版本和 SHA-256 固定在脚本中，构建
完成后可用 `file src-tauri/resources/ffmpeg/*/ffmpeg*` 检查产物。

开发时如果资源不存在，也会回退到 `PATH` 中的 `ffmpeg`。

`npm run tauri -- build --debug` 会构建本机调试安装包。CI 会运行前端构建、Rust
格式/Clippy 和单元测试；`desktop-v*` 标签触发 macOS universal 与 Windows x64 的
安装包工作流。MP3 编码使用随包提供的 LGPL `libmp3lame`，不依赖 Homebrew 或系统中的
GPL FFmpeg。

## 行为

- 支持新版 `musicex` `.mgg` / `.mflac`。
- macOS 从当前用户 QQ 音乐 plist 读取凭据；Windows 从已登录、运行中的 QQMusic.exe
  读取凭据，权限不足时才提示管理员启动。
- ekey 和登录令牌仅用于当前进程，不写入日志、磁盘或任务历史。
- 自动获取失败时可以在界面手动粘贴 ekey。
