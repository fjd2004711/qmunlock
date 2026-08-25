<p align="center">
  <img src="desktop/src-tauri/icons/icon.svg" width="112" alt="QM Unlock logo">
</p>

<h1 align="center">QM Unlock</h1>

<p align="center">macOS 与 Windows 的本地 musicex 文件处理工作台</p>

<p align="center">
  <img src="https://img.shields.io/badge/macOS-universal-151515?logo=apple&logoColor=white" alt="macOS universal">
  <img src="https://img.shields.io/badge/Windows-x64-0078D4?logo=windows&logoColor=white" alt="Windows x64">
  <img src="https://img.shields.io/badge/Tauri-2-24C8DB?logo=tauri&logoColor=white" alt="Tauri 2">
  <img src="https://img.shields.io/badge/Rust-core-DEA584?logo=rust&logoColor=white" alt="Rust core">
  <img src="https://img.shields.io/badge/license-MIT-60B932" alt="MIT license">
</p>

**把新版 QQ 音乐下载的加密文件拖进来，解析、解密、转 MP3 一次完成。**

QM Unlock 是 Rust + Tauri 2 桌面应用，面向带 `musicex` V1 footer 的 `.mgg`、`.mflac` 本地下载文件：自动识别文件、获取或接收 ekey、恢复原始 Ogg / FLAC 音频，并可直接批量转为 MP3。它支持文件和文件夹拖放、实时进度与 macOS / Windows 双平台工作流。

> **新版格式已覆盖**：项目已在 macOS QQ 音乐 `19.57+` 生成的 `musicex` 文件上验证。兼容性以文件实际带有 `musicex` V1 footer 为准，而不是以某个客户端版本号作绝对判断；Windows 亦按同一文件格式判断。

> 软件按 [MIT License](LICENSE) 以“现状”提供，不附带任何担保。使用及合规责任由使用者自行承担，详见 [免责声明](DISCLAIMER.md)。

## 目录

- [特性](#特性)
- [下载安装](#下载安装)
- [快速使用](#快速使用)
- [解密流程](#解密流程)
- [ekey 获取方式](#ekey-获取方式)
- [支持范围与局限](#支持范围与局限)
- [隐私与安全](#隐私与安全)
- [常见问题](#常见问题)
- [开发与发布](#开发与发布)

## 特性

- **跨平台**：macOS universal（Apple Silicon / Intel）和 Windows x64。
- **原生拖放**：可拖入单个文件、多个文件或整个下载文件夹。
- **实时进度**：任务逐步显示解析、获取 ekey、解密、转码的状态与进度。
- **两种 ekey 输入**：优先自动读取当前用户的 QQ 音乐登录状态；不成功时可手动粘贴自己的 ekey。
- **保留原始格式**：自动识别解密后的 Ogg、FLAC、MP3 等格式并输出。
- **可选 MP3**：使用随应用提供的 LGPL FFmpeg / libmp3lame 转码，不依赖用户另装 Homebrew 或 FFmpeg。
- **离线处理音频**：文件解析、密钥推导与解密均在本机完成；只有自动请求 ekey 时才需要网络。

## 下载安装

从 GitHub 的 **Releases** 下载对应系统的安装包：

| 平台 | 文件 | 架构 |
| --- | --- | --- |
| macOS | `QM Unlock_*.dmg` | universal（Apple Silicon / Intel） |
| Windows | `QM Unlock_*_x64-setup.exe` | x64 |

### 未签名测试包的首次运行

当前 Release 可以不签名发布和本地使用，功能没有区别；区别只在系统首次运行时的提示。

| 系统 | 可能的提示 | 处理方式 |
| --- | --- | --- |
| macOS | Gatekeeper 提示无法验证开发者 | 在 Finder 中按住 Control 点按应用，选择“打开”，再确认一次。 |
| Windows | Microsoft Defender SmartScreen 提示未知发布者 | 只从本仓库 Releases 下载；确认来源后可在“更多信息”中继续。 |

面向广泛用户正式分发时，建议启用 macOS Developer ID 签名与公证、Windows Authenticode 签名。签名并不是本地使用的前提。

## 快速使用

1. 在 QQ 音乐中下载你有权访问的 `.mgg` 或 `.mflac` 文件。
2. 打开 QM Unlock，将文件或包含文件的文件夹拖进窗口。
3. 选择输出目录：可保留解密后的原始音频，或同时转为 MP3。
4. 保持“自动获取 ekey”开启；若自动方式失败，在界面中粘贴你已取得的 ekey。
5. 点击开始，任务卡片会显示每个文件的处理状态。完成后可直接打开输出目录。

建议先用一首文件验证流程，再批量处理整个下载目录。

## 解密流程

下面是一个任务在本机的处理路径：

```text
.mgg / .mflac
       │
       ├─ 1. 解析 musicex footer
       │       └─ 读取歌曲标识和资源文件名，定位加密音频区间
       │
       ├─ 2. 获取 ekey
       │       ├─ 自动：读取当前用户 QQ 音乐的登录状态并请求 ekey
       │       └─ 手动：使用者在界面粘贴 ekey
       │
       ├─ 3. 还原 QMC2 密钥
       │       └─ Base64 → EncV2 / EncV1（TC-TEA）或原始 key
       │
       ├─ 4. 解密音频区
       │       └─ 按 key 类型使用 Map-XOR 或分段 RC4 变体
       │
       ├─ 5. 识别输出格式
       │       └─ Ogg / FLAC / MP3 / 其他二进制格式
       │
       └─ 6. 可选转码
               └─ FFmpeg → MP3
```

应用不会上传 `.mgg` / `.mflac` 文件。自动获取 ekey 时，客户端会向服务端发送请求所需的歌曲标识、资源名和当前登录认证信息；解密和转码仍在本机进行。

## ekey 获取方式

### 自动获取（默认）

| 平台 | 方式 | 前提 |
| --- | --- | --- |
| macOS | 读取当前用户 QQ 音乐的本地登录信息 | QQ 音乐已登录 |
| Windows | 从正在运行、已登录的 QQ 音乐进程读取可用认证信息 | QQ 音乐正在运行；权限级别匹配 |

自动获取失败时，应用会给出可操作的原因。Windows 客户端的内部实现可能随版本变化，因而手动 ekey 是始终可用的后备方式。

### 手动 ekey（推荐的稳定后备）

在界面中选择手动模式，粘贴与该文件匹配的 ekey 后开始任务。ekey 只保留在当前运行内存中，不会写入任务历史、日志或配置文件。

### macOS Hook（高级可选后备）

仓库保留了 [`frida/`](frida) 下的 macOS 调试脚本。它适合自动读取不可用、且你需要从自己的本地客户端处理路径中取得 ekey 的情况。

- **不是桌面应用的必经步骤**；优先使用自动获取或手动 ekey。
- 仓库不包含 QQ 音乐应用本体或其副本。
- 该方案需要本机已安装的官方客户端、额外调试环境和较高的排查能力；QQ 音乐更新后可能失效。
- 请勿在 issue、截图、日志或提交中分享捕获到的 ekey、登录信息或真实音频文件。

## 支持范围与局限

| 项目 | 当前情况 |
| --- | --- |
| 新版输入格式 | 支持带 `musicex` V1 footer 的 `.mgg` / `.mflac`；该格式已在 macOS QQ 音乐 `19.57+` 场景验证。 |
| 判断方式 | 以文件的 `musicex` footer 为准，不承诺某一客户端版本的所有资源都使用同一种封装。 |
| 旧格式 | 旧 QMC / QTag / STag 及其他音乐平台格式不在当前桌面端支持范围。 |
| ekey | 每个资源需要匹配的 ekey；应用不能凭空生成，也不能替代服务端授权。 |
| Windows 自动读取 | 依赖客户端版本和进程权限。若 QQ 音乐以管理员运行，QM Unlock 也可能需要相同权限。 |
| 损坏文件 | 下载不完整、footer 异常或 ekey 不匹配时无法正确输出音频。 |
| 转码 | MP3 是可选后处理；关闭转码时会保留识别到的原始音频格式。 |
| 账号与权限 | 应用无法改变帐号对资源的访问权限，也不承诺所有客户端版本都能自动取得 ekey。 |

## 隐私与安全

- 登录信息和 ekey 仅用于当前任务，不写入磁盘、任务历史或应用日志。
- 项目 `.gitignore` 默认排除本地捕获、真实 ekey、下载样例和构建输出。
- 不要在 issue、PR、日志或截图中提交 `authst`、ekey、QQ 号、数据库、plist、进程内存或真实音乐文件。
- 安全问题请遵循 [SECURITY.md](SECURITY.md)。

## 常见问题

<details>
<summary><strong>Windows 显示已发现 QQ 音乐，但没有读取到 authst</strong></summary>

新版 QQ 音乐可能不再把该信息保留在可读取的进程内存中；重新登录也不一定改变结果。确认 QQ 音乐已登录且两者权限级别相同后，仍失败时请改用手动 ekey。

</details>

<details>
<summary><strong>macOS 提示“无法打开”或“无法验证开发者”</strong></summary>

这是未签名测试包的 Gatekeeper 提示，不代表应用功能异常。请从 Releases 重新下载，然后在 Finder 中按住 Control 点按应用并选择“打开”。

</details>

<details>
<summary><strong>解密完成但无法播放</strong></summary>

先关闭 MP3 转码并检查原始输出格式；随后确认输入文件完整、ekey 与资源匹配。若问题可复现，请使用脱敏后的错误信息提交 Bug report。

</details>

<details>
<summary><strong>我可以不安装 FFmpeg 吗？</strong></summary>

可以。发布安装包已包含用于转码的 LGPL FFmpeg；开发模式下若随包资源不存在，才会尝试使用系统 PATH 中的 `ffmpeg`。

</details>

## 开发与发布

### 本地开发

前置条件：Node.js 20+、Rust stable，以及对应平台的 Tauri 系统依赖。

```bash
cd desktop
npm ci
npm run tauri dev
```

### 验证

```bash
cd desktop
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml

# 根目录的 Python 算法原型测试
cd ..
python3 tests/test_decrypt.py
```

### CI 与 Release

- Pull Request 和主分支推送会运行 macOS / Windows 构建验证。
- 推送 `vX.Y.Z` 标签会构建 macOS universal 与 Windows x64 安装包，并创建未签名 GitHub Release。
- 完整发布步骤见 [docs/RELEASING.md](docs/RELEASING.md)，变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 项目结构

```text
desktop/                  Tauri 2 桌面应用
├── src/                  React / TypeScript 界面
├── src-tauri/src/core/   Rust 解密、凭据、任务核心
└── src-tauri/resources/  随包 FFmpeg 与许可材料
qmunlock/                 Python 算法原型
frida/                    macOS 高级可选调试脚本
.github/                  CI、Release、Issue 与 PR 配置
```

## 贡献与许可

欢迎提交兼容性、体验和测试改进。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，并确保不包含任何帐号凭据、ekey 或真实媒体文件。

项目代码采用 [MIT License](LICENSE)。随包 FFmpeg / libmp3lame 按其自身 LGPL 条款分发，许可和源码说明位于 [`desktop/src-tauri/resources/ffmpeg`](desktop/src-tauri/resources/ffmpeg)。
