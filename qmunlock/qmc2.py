"""QMC2 (musicex) 核心解密算法 —— 纯函数，无 I/O，无外部依赖。

QQ音乐 Mac 新版使用 musicex 格式存加密音频 (.mgg / .mflac / .mmp4)。
解密链路：ekey(base64) → 可选 EncV2 双层 TEA 剥壳 → 密钥推导(TEA-CBC) →
按密钥长度走 Map-XOR(≤300B) 或 分段 RC4(>300B)。

本模块只负责「拿到 ekey 字节 + 密文 → 明文」，不涉及 ekey 怎么来、文件怎么读。
"""
import base64

# ────────────────────────────────────────────────────────────────
# Tencent-TEA（big-endian，16 轮，CBC + 自定义 salt/zero 头）
# ────────────────────────────────────────────────────────────────
def _be_read(b, o):
    return int.from_bytes(b[o:o+4], 'big')


def _be_write(b, o, v):
    b[o] = (v >> 24) & 0xff
    b[o + 1] = (v >> 16) & 0xff
    b[o + 2] = (v >> 8) & 0xff
    b[o + 3] = v & 0xff


def _tea_block_dec(block, k):
    """对单个 8 字节块做 TEA 解密（in-place）。k = 4 个大端 uint32。"""
    v0 = _be_read(block, 0)
    v1 = _be_read(block, 4)
    M = 0xffffffff
    delta = 0x9E3779B9
    sm = 0xE3779B90
    for _ in range(16):
        t1 = ((v0 << 4) + k[2]) & M
        t2 = (v0 + sm) & M
        t3 = ((v0 >> 5) + k[3]) & M
        v1 = (v1 - (t1 ^ t2 ^ t3)) & M
        t1 = ((v1 << 4) + k[0]) & M
        t2 = (v1 + sm) & M
        t3 = ((v1 >> 5) + k[1]) & M
        v0 = (v0 - (t1 ^ t2 ^ t3)) & M
        sm = (sm - delta) & M
    _be_write(block, 0, v0 & M)
    _be_write(block, 4, v1 & M)


def tencent_tea_dec(data, key):
    """Tencent-TEA 解密（CBC 变体）。

    结构：[salt(1B)] [7 零字节] [加密块...]；首 8 字节是 IV，
    明文长度编码在 salt 头（dest[0]&0x07 为 padLen）。
    """
    if len(data) % 8 != 0 or len(data) < 16:
        raise ValueError("tea: 长度非法")
    tk = [_be_read(key, 0), _be_read(key, 4), _be_read(key, 8), _be_read(key, 12)]
    dest = bytearray(data[:8])
    _tea_block_dec(dest, tk)
    padLen = dest[0] & 0x07
    outLen = len(data) - 1 - padLen - 2 - 7  # 1 salt + 2 saltLen + 7 zero
    if outLen < 0:
        raise ValueError("tea: outLen<0")
    out = bytearray(outLen)
    ivPrev = bytearray(8)
    ivCur = bytearray(data[:8])
    state = {'inPos': 8, 'destIdx': 1 + padLen}

    def crypt_block():
        ivPrev[:], ivCur[:] = ivCur[:], data[state['inPos']:state['inPos'] + 8]
        for i in range(8):
            dest[i] ^= data[state['inPos'] + i]
        _tea_block_dec(dest, tk)
        state['inPos'] += 8
        state['destIdx'] = 0

    # 跳过 salt 段
    i = 1
    while i <= 2:
        if state['destIdx'] < 8:
            state['destIdx'] += 1
            i += 1
        else:
            crypt_block()
    op = 0
    while op < outLen:
        if state['destIdx'] < 8:
            out[op] = dest[state['destIdx']] ^ ivPrev[state['destIdx']]
            state['destIdx'] += 1
            op += 1
        else:
            crypt_block()

    # Tencent-TEA appends seven zero bytes after the payload.  This is the
    # integrity check that distinguishes an EncV1 body from arbitrary raw API
    # key bytes of a multiple-of-eight length.
    checked = 0
    while checked < 7:
        if state['destIdx'] < 8:
            if (dest[state['destIdx']] ^ ivPrev[state['destIdx']]) != 0:
                raise ValueError("tea: zero padding invalid")
            state['destIdx'] += 1
            checked += 1
        else:
            crypt_block()
    return bytes(out)


# ────────────────────────────────────────────────────────────────
# 密钥推导：EncV2 剥壳 + EncV1 头/体
# ────────────────────────────────────────────────────────────────
SIMPLE_KEY = bytes([0x69, 0x56, 0x46, 0x38, 0x2B, 0x20, 0x15, 0x0B])
V2K1 = bytes([0x33, 0x38, 0x36, 0x5A, 0x4A, 0x59, 0x21, 0x40, 0x23, 0x2A, 0x24, 0x25, 0x5E, 0x26, 0x29, 0x28])
V2K2 = bytes([0x2A, 0x2A, 0x23, 0x21, 0x28, 0x23, 0x24, 0x25, 0x26, 0x5E, 0x61, 0x31, 0x63, 0x5A, 0x2C, 0x54])
V2P = b"QQMusic EncV2,Key:"


def _b64d(s):
    s = s.encode() if isinstance(s, str) else s
    return base64.b64decode(s + b'=' * (-len(s) % 4))


def derive_key(ekey_b64):
    """把 ekey（base64 串）还原成最终解密密钥字节。

    1. base64 解码
    2. 若以 "QQMusic EncV2,Key:" 开头 → 两层 TEA(V2K1,V2K2) + base64 得到 EncV1
    3. EncV1：前 8 字节做头，与 SIMPLE_KEY 交错组成 TEA 密钥，解出体
    4. 返回 头(8B) + 体
    """
    dec = _b64d(ekey_b64)
    if dec[:len(V2P)] == V2P:
        buf = tencent_tea_dec(dec[len(V2P):], V2K1)
        buf = tencent_tea_dec(buf, V2K2)
        dec = _b64d(buf)
    if len(dec) < 16:
        raise ValueError("ekey 过短")
    tk = bytearray(16)
    for i in range(8):
        tk[2 * i] = SIMPLE_KEY[i]
        tk[2 * i + 1] = dec[i]
    # GetEVkey may return either EncV1 or already-decoded raw key bytes.  A
    # valid EncV1 body must pass Tencent-TEA's trailing-zero integrity check.
    try:
        body = tencent_tea_dec(dec[8:], bytes(tk))
    except ValueError:
        return dec
    return dec[:8] + body


# ────────────────────────────────────────────────────────────────
# 数据层解密：Map-XOR（密钥 ≤ 300B） / 分段 RC4（> 300B）
# ────────────────────────────────────────────────────────────────
def _map_mask(key, off):
    if off > 0x7FFF:
        off %= 0x7FFF
    size = len(key)
    idx = (off * off + 71214) % size
    v = key[idx] & 0xff
    r = ((idx & 7) + 4) % 8
    # This looks like a rotate, but QQ Music's QMStreamEncrypt uses the
    # historical mapL expression ``(value << r) | (value >> r)``.  It is
    # deliberately *not* a normal rotate-right operand of ``8 - r``.
    # Keeping that quirk is required for current musicex/QMC2 files.
    return ((v << r) | (v >> r)) & 0xff if r else v


def map_decrypt(buf, key, off0=0):
    for i in range(len(buf)):
        buf[i] ^= _map_mask(key, off0 + i)
    return buf


class RC4:
    """QMC2 的「伪 RC4」：前 128 字节用密钥表查找，其后按 5120 字节分段、
    每段按段号重新计算 skip 后再走 KSA/PRGA 变体。"""
    SEG = 5120
    FIRST = 128

    def __init__(self, key):
        self.key = key
        n = len(key)
        self.n = n
        box = [i & 0xff for i in range(n)]
        j = 0
        for i in range(n):
            j = (j + (box[i] & 0xff) + (key[i % n] & 0xff)) % n
            box[i], box[j] = box[j], box[i]
        self.box = box
        # hash：用乘法找第一个落在 (0, n) 递增区间的值
        h = 1
        for i in range(n):
            v = key[i] & 0xff
            if v == 0:
                continue
            nxt = (h * v) & 0xffffffff
            if nxt == 0 or nxt <= h:
                break
            h = nxt
        self.hash = h

    def _seg_skip(self, id_):
        seed = self.key[id_ % self.n] & 0xff
        if seed == 0:
            return 0
        return int((self.hash / ((id_ + 1) * seed)) * 100) % self.n

    def _a_into(self, buf, off, length, offset):
        b = self.box[:]
        j = 0
        k = 0
        skipLen = (offset % self.SEG) + self._seg_skip(offset // self.SEG)
        i = -skipLen
        while i < length:
            j = (j + 1) % self.n
            k = ((b[j] & 0xff) + k) % self.n
            b[j], b[k] = b[k], b[j]
            if i >= 0:
                buf[off + i] ^= b[((b[j] & 0xff) + (b[k] & 0xff)) % self.n] & 0xff
            i += 1

    def decrypt_into(self, buf, off0=0):
        offset = off0
        to = len(buf)
        proc = 0
        if offset < self.FIRST:
            bs = min(to, self.FIRST - offset)
            for i in range(bs):
                buf[proc + i] ^= self.key[self._seg_skip(offset + i)] & 0xff
            offset += bs
            to -= bs
            proc += bs
            if to == 0:
                return
        if offset % self.SEG != 0:
            bs = min(to, self.SEG - offset % self.SEG)
            self._a_into(buf, proc, bs, offset)
            offset += bs
            to -= bs
            proc += bs
            if to == 0:
                return
        while to > self.SEG:
            self._a_into(buf, proc, self.SEG, offset)
            offset += self.SEG
            to -= self.SEG
            proc += self.SEG
        if to > 0:
            self._a_into(buf, proc, to, offset)


# ────────────────────────────────────────────────────────────────
# 对外主函数
# ────────────────────────────────────────────────────────────────
def detect_fmt(b):
    if b[:3] == b'ID3':
        return 'mp3'
    if b[:4] == b'fLaC':
        return 'flac'
    if b[:4] == b'OggS':
        return 'ogg'
    if b[4:8] == b'ftyp':
        return 'm4a'
    if b[0] == 0xFF and b[1] in (0xF2, 0xF3, 0xFB):
        return 'mp3'
    return 'bin'


def decrypt_qmc2(encrypted, ekey_b64):
    """核心：密文字节 + ekey(base64) → 明文字节。

    encrypted: 已去掉 musicex footer 的音频密文
    ekey_b64:  GetEVkey API 返回的 ekey 字符串
    返回: (明文字节, 格式名)
    """
    rk = derive_key(ekey_b64)
    audio = bytearray(encrypted)
    if len(rk) > 300:
        RC4(rk).decrypt_into(audio, 0)
    else:
        map_decrypt(audio, rk)
    return bytes(audio), detect_fmt(audio)
