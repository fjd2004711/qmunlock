# Security policy

## Sensitive data

不要在 issue、Pull Request、日志、截图或测试文件中提交：

- `authst`、access token、refresh token、cookie 或 ekey；
- QQ 音乐本地数据库、plist、进程内存转储；
- 可识别帐号、歌曲或下载来源的真实文件。

如果不慎提交了凭据，请立即在对应服务中使其失效，并从 Git 历史中清除；仅删除工作区文件不够。

## Reporting a vulnerability

在仓库启用 GitHub Security Advisories 后，请用私密报告功能提交漏洞。启用前，请不要公开披露可利用的细节；通过仓库所有者提供的私密联系方式报告，并附上复现步骤、影响范围和修复建议。
