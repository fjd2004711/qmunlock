# Contributing

欢迎修复兼容性、界面和测试问题。提交前请先确认改动不包含帐号凭据、ekey、真实加密音乐文件或其他个人数据。

在 `desktop/` 目录运行：

```bash
npm ci
npm run build
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

如果改动根目录 Python 原型，也请运行：

```bash
python3 -m pytest tests/ -q
```

请在 Pull Request 中说明测试平台、QQ 音乐客户端版本（如适用）和验证方式；不要粘贴任何凭据或 ekey。
