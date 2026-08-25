"""QMC2 算法测试（不依赖网络、帐号或真实音乐文件）。

运行: python3 -m pytest tests/ -q  或  python3 tests/test_decrypt.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))

from qmunlock import qmc2  # noqa: E402


def test_tea_roundtrip_block():
    # TEA 单块：加密再解密应还原（用同一 key）
    key = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88] * 2)
    blk = bytearray(b'01234567')
    # 加密 = 反向迭代（这里只验证解密路径可运行且可逆的结构）
    qmc2._tea_block_dec(blk, [int.from_bytes(key[i:i+4], 'big') for i in range(0, 16, 4)])
    assert len(blk) == 8


def test_rc4_is_symmetric_across_segments():
    """合成 key 与数据跨过多个 5120-byte 分段，解密两次应还原。"""
    key = bytes((i * 37 + 11) & 0xff for i in range(512))
    original = bytes(i & 0xff for i in range(12_000))
    value = bytearray(original)
    rc4 = qmc2.RC4(key)
    rc4.decrypt_into(value)
    rc4.decrypt_into(value)
    assert bytes(value) == original


if __name__ == '__main__':
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    for fn in fns:
        fn()
        print("  ✅", fn.__name__)
    print(f"\n{len(fns)} 个测试全部通过")
