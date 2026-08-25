## Summary

Describe the change and why it is needed.

## Verification

- [ ] `npm run build`
- [ ] `cargo fmt --manifest-path src-tauri/Cargo.toml --check`
- [ ] `cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings`
- [ ] `cargo test --manifest-path src-tauri/Cargo.toml`

## Privacy check

- [ ] This change does not include authst, ekey, account details, real downloaded media, or local capture logs.
