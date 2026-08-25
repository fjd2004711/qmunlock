# Releasing QM Unlock

## Prerequisites

- The `main` branch passes the Verify workflow.
- Update `desktop/src-tauri/tauri.conf.json`, `desktop/package.json`, and `CHANGELOG.md` with the release version.
- Review `git status` and confirm that no credentials, ekeys, captures, test music, or local build output are included.

## Unsigned release

1. Create and push a tag in the form `vX.Y.Z`.
2. The **Release desktop app** workflow builds macOS arm64 (Apple Silicon), macOS x64 (Intel), and Windows x64 packages.
3. It creates a GitHub Release and attaches the `.dmg`, `.exe`, and `.msi` files.
4. Test each target package on a clean machine before marking the release as stable.

The default workflow is intentionally unsigned and requires no secrets.

## Optional signing

- **macOS:** use a Developer ID Application certificate and notarize the finished application with Apple.
- **Windows:** sign the installer and executable with an Authenticode certificate. An EV certificate can improve SmartScreen reputation over time.

Do not put certificate files, passwords, Apple credentials, ekeys, or QQ Music credentials in the repository. Store release credentials only as protected GitHub Actions secrets.
