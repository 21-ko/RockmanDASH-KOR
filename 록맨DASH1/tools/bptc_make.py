"""BPTC 패치 파일 생성기 (installer/bptc.py 의 apply_patch 와 짝).

형식: 'BPTC' | ver(1) | 원본 크기(8) | 결과 크기(8) | 원본 CRC(4) | 결과 CRC(4)
      | 압축 delta 크기(8) | zlib(delta)
delta: 0x01 COPY(원본 offset 4, 길이 4) / 0x02 ADD(길이 4, 데이터)
"""
import struct
import zlib

BLOCK = 2048


def make_patch(original_file, new_file, patch_file):
    with open(original_file, 'rb') as f:
        orig = f.read()
    with open(new_file, 'rb') as f:
        new = f.read()

    # 같은 위치의 섹터끼리 비교해서 COPY/ADD 구간으로 묶는다
    runs = []  # (is_copy, start, end)
    for pos in range(0, len(new), BLOCK):
        end = min(pos + BLOCK, len(new))
        same = end <= len(orig) and new[pos:end] == orig[pos:end]
        if runs and runs[-1][0] == same:
            runs[-1][2] = end
        else:
            runs.append([same, pos, end])

    delta = bytearray()
    for is_copy, start, end in runs:
        if is_copy:
            delta += b'\x01' + struct.pack('>II', start, end - start)
        else:
            delta += b'\x02' + struct.pack('>I', end - start) + new[start:end]
    compressed = zlib.compress(bytes(delta), 9)

    with open(patch_file, 'wb') as f:
        f.write(b'BPTC' + struct.pack('>B', 1))
        f.write(struct.pack('>QQ', len(orig), len(new)))
        f.write(struct.pack('>II', zlib.crc32(orig), zlib.crc32(new)))
        f.write(struct.pack('>Q', len(compressed)))
        f.write(compressed)
