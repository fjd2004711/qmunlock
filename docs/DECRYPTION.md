# 解密技术说明

本文面向开发者，说明 QM Unlock 如何在本机处理带 `musicex V1 footer` 的 `.mgg`、`.mflac` 与 `.mmp4` 文件。它描述的是当前实现与可验证的文件特征；QQ 音乐客户端更新后，文件结构和认证链路仍可能变化。

> 不要在 issue、日志、截图或提交中提供 ekey、`authst`、账号信息或真实音频文件。

## 总览

```text
加密文件
  │
  ├─ ① 读取 musicex footer ──→ song MID + 资源文件名 + 音频区长度
  │
  ├─ ② 取得匹配 ekey ───────→ 手动输入 / 本机登录态请求
  │
  ├─ ③ 推导 QMC2 key ───────→ Base64 → EncV2 / EncV1 / raw key
  │
  ├─ ④ 按绝对偏移流式解密 ──→ Map-XOR 或分段 RC4 变体
  │
  ├─ ⑤ 校验音频头 ─────────→ Ogg / FLAC / M4A / MP3
  │
  └─ ⑥ 写出原始音频 ───────→ 可选 FFmpeg 转 MP3
```

文件解析、密钥推导、解密和转码均在本机进行。只有选择“自动获取 ekey”时，应用才会向 QQ 音乐接口发送取得该资源 ekey 所需的元数据与当前登录认证信息；不会上传音频文件。

## 1. `musicex V1 footer`：定位音频区

QM Unlock 不单靠扩展名判断文件。它会先从文件末尾读取 16 字节 trailer：

| 字段 | 作用 |
| --- | --- |
| `0..4` | 小端 `u32`，整个 footer 的长度 |
| `8..16` | 固定标识 `musicex\0` |

footer 至少为 192 字节，且长度不能超过文件总长度。通过校验后，应用从 `文件总长度 - footer 长度` 处读取 footer，并从其中的 UTF-16LE 定长字段取出：

| footer 偏移 | 长度 | 内容 | 用途 |
| --- | ---: | --- | --- |
| `0x0c` | 60 bytes | 歌曲 MID | 自动请求 ekey |
| `0x48` | 68 bytes | 原始资源文件名 | 自动请求 ekey、扩展名白名单 |

真正参与解密的只有文件开头到 footer 起点之间的字节：`audio_length = 文件总长度 - footer 长度`。footer 不会写入输出音频。

资源文件名必须是 `.mgg`、`.mflac` 或 `.mmp4` 之一；否则任务会在解析阶段停止。这避免把非目标文件送进后续算法。

### 不支持的历史 QMC 格式

本项目只实现当前 `musicex V1` / QMC2 链路，**不兼容旧 QMC 体系**。包括但不限于 `.qmc*`、`.bkcmp3`、QTag、STag，以及旧版 QQ 音乐下载但没有 `musicex V1 footer` 的文件。即使文件扩展名恰好是 `.mgg`、`.mflac` 或 `.mmp4`，只要尾部没有有效 footer，也会被拒绝。

## 2. ekey：获取与使用边界

每个资源都需要匹配的 ekey。应用提供两条路径：

| 方式 | 流程 | 常见前提 |
| --- | --- | --- |
| 自动 | 从本机已登录 QQ 音乐读取可用认证状态，再以 footer 中的 MID 与资源名请求 ekey | QQ 音乐已登录；Windows 下两者权限级别一致 |
| 手动 | 用户粘贴与当前文件匹配的 ekey | ekey 必须对应同一资源 |

自动请求使用 `music.vkey.GetEVkey`，并携带资源文件名、歌曲 MID 与当前登录态。响应中只提取 ekey 字段用于当前任务。ekey 和登录信息不会被写入任务历史、配置或应用日志。

自动方式失败并不等于文件无法解密：Windows 客户端权限或内存布局变化都可能影响本地认证信息的读取，此时可使用手动 ekey。

## 3. ekey 到 QMC2 key

界面收到的 ekey 是编码后的材料，并非总能直接作为解密 key 使用。`qmc2::derive_key` 按以下顺序处理：

1. 对 ekey 做 Base64 解码；无效编码或少于 8 字节会报错。
2. 如果数据带 `QQMusic EncV2,Key:` 前缀，先后进行两轮 TC-TEA 解封，再对内层文本进行 Base64 解码。
3. 解码结果刚好为 8 字节时，直接作为 key。
4. 更长的数据会按照 EncV1 的规则构造 TC-TEA key，并尝试解开剩余部分：成功时，将前 8 字节与解出的主体拼成最终 QMC2 key。
5. 有些客户端/接口会返回原始 key。若 EncV1 解封失败，或尾部完整性校验不通过，代码会保留原始解码结果，而不会把它误判为 EncV1。

TC-TEA 的实现采用 8 字节分组、16 轮解密，并检查填充、两字节 salt 和末尾 7 个零字节。这个尾部检查尤其重要：它避免“长度恰好是 8 的倍数”的原始 key 被错误地当成有效密文。

## 4. QMC2 音频区解密

解密使用绝对文件偏移，因此可以安全地按块流式处理。当前块大小为 **256 KiB**：首块先用于识别输出格式，之后逐块解密并写出；每一块都携带已经处理的绝对 offset，不能把每块都当作 offset 为 0 的独立数据。

根据最终 key 长度选择分支：

| key 长度 | 算法分支 | 特点 |
| --- | --- | --- |
| `≤ 300` bytes | Map-XOR | 每个字节按位置选择 key 字节并异或 |
| `> 300` bytes | 分段 RC4 变体 | 前 128 字节与其后 5120 字节分段采用不同处理 |

### Map-XOR

对当前音频区的每个位置 `p`，实现先将位置折回 `0x7fff` 周期，再用下式选择 key 下标：

```text
offset = p mod 0x7fff
index  = (offset² + 71214) mod key_length
shift  = ((index & 7) + 4) & 7
```

随后将该 key 字节经过客户端兼容的 `mapL` 变换并与密文字节异或。这里有一个容易踩到的兼容性细节：历史 `mapL` 并不是标准循环移位，而是将同一字节的左移与右移结果相或后取低 8 位。QM Unlock 保留这一行为；把它替换成正常的 rotate，会导致当前 `musicex` 文件输出损坏。

### 分段 RC4 变体

长 key 使用由 key 初始化的置换表。前 128 字节按 key 与位置相关的索引直接异或；后续数据以 **5120 字节**为一个逻辑段。每段从初始置换表重新开始，根据段号得到确定性的 skip 长度，再生成该段所需的伪随机字节流。

这也是解密必须传入绝对 offset 的原因：任意块跨越 128 字节边界或 5120 字节边界时，算法都需要自动切换到正确分支和段内位置。

## 5. 输出格式识别与写入

首个已解密块会按魔数识别容器，而不是根据输入扩展名决定输出扩展名：

| 识别特征 | 输出扩展名 |
| --- | --- |
| `OggS` | `.ogg` |
| `fLaC` | `.flac` |
| 第 4–7 字节为 `ftyp` | `.m4a` |
| `ID3` 或首字节为 `0xff` | `.mp3` |

未匹配任何特征时，任务立即报出“ekey 无效，或文件不是受支持的 QMC2 音频”，不会继续写出看似成功的二进制垃圾数据。

原始音频会以输入文件名作为 stem 输出；若目标目录已有同名文件，则自动追加 ` (1)`、` (2)` 等序号，避免覆盖已有文件。

选择“转 MP3”且原始格式不是 MP3 时，应用会调用随包的 FFmpeg / libmp3lame，以 `-q:a 2` 进行音频转码。转码成功且输出文件大于 1 KiB 后，才删除临时的原始容器文件；选择“保留原始格式”则不会运行 FFmpeg。

## 6. 进度、校验与故障定位

界面对一个任务依次显示 `parse`、`ekey`、`decrypt`、`transcode` 四个阶段。`decrypt` 阶段按已处理音频字节数计算进度；`transcode` 是单独的后处理阶段。

| 现象 | 优先检查 |
| --- | --- |
| 未识别为 musicex 文件 | 文件是否下载完整、尾部是否存在 `musicex\0`、footer 长度是否合理 |
| 自动获取 ekey 失败 | QQ 音乐是否已登录；Windows 下应用和 QQ 音乐是否以相同权限运行 |
| 识别到 footer 但解密后没有音频头 | 手动 ekey 是否对应同一首资源；文件是否属于受支持的 QMC2 链路 |
| 原始格式可出但 MP3 转码失败 | 发布包中的 FFmpeg 是否完整；开发环境中 `ffmpeg` 是否在 `PATH` |
| 输出不能播放 | 先关闭 MP3 转码保留原始文件，再确认 ekey、下载完整性与播放器对该容器/编码的支持 |

## 代码入口与回归测试

| 模块 | 责任 |
| --- | --- |
| [`footer.rs`](../desktop/src-tauri/src/core/footer.rs) | trailer、footer 与 UTF-16 字段解析 |
| [`ekey.rs`](../desktop/src-tauri/src/core/ekey.rs) | 自动 ekey 请求 |
| [`qmc2.rs`](../desktop/src-tauri/src/core/qmc2.rs) | ekey 推导、TC-TEA、Map-XOR、RC4 与格式识别 |
| [`decrypt.rs`](../desktop/src-tauri/src/core/decrypt.rs) | 流式读写、进度、命名与 FFmpeg 转码 |
| [`commands.rs`](../desktop/src-tauri/src/commands.rs) | Tauri 命令与前端进度事件 |

提交算法修改前，至少运行：

```bash
cd desktop
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings

cd ..
python3 tests/test_decrypt.py
```

测试用例必须使用合成数据或已脱敏的固定向量，不能提交真实音乐、账号凭据或 ekey。
