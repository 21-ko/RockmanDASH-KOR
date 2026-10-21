"""ISO9660(UMD) 이미지 안의 파일을 교체하는 도구.

UMD-replace 방식과 동일하게 동작한다.
  - 새 파일이 기존 섹터 수 안에 들어가면 제자리에 쓰고, 남는 부분은 0으로 채운다.
  - 들어가지 않으면 기존 자리를 0으로 지우고 이미지 끝에 새로 붙인다.
"""
import struct

SECTOR = 2048


def _sectors(size):
    return (size + SECTOR - 1) // SECTOR


class IsoImage:
    def __init__(self, path, writable=True):
        self.f = open(path, 'r+b' if writable else 'rb')
        self.f.seek(16 * SECTOR)
        pvd = self.f.read(SECTOR)
        if pvd[1:6] != b'CD001':
            raise ValueError('ISO9660 이미지가 아닙니다: ' + path)
        self.volume_blocks = struct.unpack('<I', pvd[80:84])[0]
        root = pvd[156:190]
        # 파일 경로(대문자) -> (디렉터리 레코드 위치, 시작 LBA, 크기)
        self.entries = {}
        self._walk(struct.unpack('<I', root[2:6])[0], struct.unpack('<I', root[10:14])[0], '')

    def _walk(self, lba, size, prefix):
        self.f.seek(lba * SECTOR)
        data = self.f.read(size)
        i = 0
        while i < len(data):
            length = data[i]
            if length == 0:
                i = (i // SECTOR + 1) * SECTOR
                continue
            rec = data[i:i + length]
            extent = struct.unpack('<I', rec[2:6])[0]
            data_len = struct.unpack('<I', rec[10:14])[0]
            name = rec[33:33 + rec[32]]
            if name not in (b'\x00', b'\x01'):
                name = name.decode('ascii').split(';')[0]
                if rec[25] & 2:
                    self._walk(extent, data_len, prefix + name + '/')
                else:
                    self.entries[(prefix + name).upper()] = (lba * SECTOR + i, extent, data_len)
            i += length

    def read(self, path):
        _, extent, size = self.entries[path.upper()]
        self.f.seek(extent * SECTOR)
        return self.f.read(size)

    def replace(self, path, data):
        key = path.upper()
        rec_pos, extent, old_size = self.entries[key]
        old_sectors = _sectors(old_size)
        new_sectors = _sectors(len(data))

        if new_sectors <= old_sectors:
            self.f.seek(extent * SECTOR)
            self.f.write(data + bytes(old_sectors * SECTOR - len(data)))
        else:
            self.f.seek(extent * SECTOR)
            self.f.write(bytes(old_sectors * SECTOR))
            extent = self.volume_blocks
            self.f.seek(extent * SECTOR)
            self.f.write(data + bytes(new_sectors * SECTOR - len(data)))
            self.volume_blocks += new_sectors
            self.f.seek(16 * SECTOR + 80)
            self.f.write(struct.pack('<I', self.volume_blocks) + struct.pack('>I', self.volume_blocks))

        # 디렉터리 레코드의 시작 LBA와 크기 갱신 (리틀/빅 엔디언 양쪽)
        self.f.seek(rec_pos + 2)
        self.f.write(struct.pack('<I', extent) + struct.pack('>I', extent)
                     + struct.pack('<I', len(data)) + struct.pack('>I', len(data)))
        self.entries[key] = (rec_pos, extent, len(data))

    def close(self):
        self.f.close()
