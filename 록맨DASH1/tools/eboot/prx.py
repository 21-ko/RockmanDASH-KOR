"""PSP PRX(ELF, e_type 0xFFA0) 실행파일 다루기.

BOOT.BIN 은 0번 지점에 맞춰 링크된 PRX 이고, 게임은 0x08804000 에 올라간다.
  세그먼트 0 : .text/.rodata  (vaddr 0x000000)
  세그먼트 1 : .data/.bss     (vaddr 0x245200)
로더가 재배치(relocation)를 적용하므로, 재배치가 걸린 워드를 고치면 로더가 그 값을 또 바꾼다.
"""
import struct

LOAD_ADDR = 0x08804000
SHT_PSPREL = 0x700000A0
R_MIPS_32 = 2


def align(value, n):
    return (value + n - 1) // n * n


class Segment:
    def __init__(self, ph_offset, fields):
        self.ph_offset = ph_offset  # 프로그램 헤더 위치
        (self.type, self.offset, self.vaddr, self.paddr,
         self.filesz, self.memsz, self.flags, self.align) = fields

    @property
    def addr(self):
        """메모리 주소."""
        return LOAD_ADDR + self.vaddr

    def pack(self):
        return struct.pack('<8I', self.type, self.offset, self.vaddr, self.paddr,
                           self.filesz, self.memsz, self.flags, self.align)


class Prx:
    def __init__(self, data):
        self.data = bytearray(data)
        if self.data[:4] != b'\x7fELF' or struct.unpack_from('<H', self.data, 16)[0] != 0xFFA0:
            raise ValueError('PSP PRX 가 아닙니다 (복호화된 BOOT.BIN 이 필요합니다)')
        phoff, shoff = struct.unpack_from('<II', self.data, 28)
        phnum, _, shnum = struct.unpack_from('<HHH', self.data, 44)
        self.segments = [Segment(phoff + i * 32, struct.unpack_from('<8I', self.data, phoff + i * 32))
                         for i in range(phnum)]
        self.sections = [struct.unpack_from('<10I', self.data, shoff + i * 40) for i in range(shnum)]
        self.relocs = self._read_relocs()

    def _read_relocs(self):
        """메모리 주소 -> [(타입, 기준 세그먼트)]"""
        relocs = {}
        for sh in self.sections:
            if sh[1] != SHT_PSPREL:
                continue
            for pos in range(sh[4], sh[4] + sh[5], 8):
                offset, info = struct.unpack_from('<II', self.data, pos)
                seg = self.segments[(info >> 8) & 0xFF]
                relocs.setdefault(seg.addr + offset, []).append((info & 0xFF, (info >> 16) & 0xFF))
        return relocs

    def file_offset(self, addr, size=1):
        """메모리 주소 → 파일 오프셋 (파일에 들어 있는 부분만)."""
        for seg in self.segments:
            if seg.addr <= addr and addr + size <= seg.addr + seg.filesz:
                return seg.offset + addr - seg.addr
        raise ValueError('파일에 없는 주소: 0x{:08X}'.format(addr))

    def read(self, addr, size):
        off = self.file_offset(addr, size)
        return bytes(self.data[off:off + size])

    def write(self, addr, data):
        off = self.file_offset(addr, len(data))
        self.data[off:off + len(data)] = data

    def pointer_value(self, at, target):
        """at 에 있는 포인터가 로드 후 target 을 가리키게 하려면 파일에 써야 할 값.
        (R_MIPS_32 재배치는 기준 세그먼트의 주소를 더한다)"""
        relocs = self.relocs.get(at, [])
        if len(relocs) != 1 or relocs[0][0] != R_MIPS_32:
            raise ValueError('0x{:08X} 는 재배치되는 포인터가 아닙니다'.format(at))
        return target - self.segments[relocs[0][1]].addr

    def extend_segment(self, index, extra):
        """세그먼트를 extra 바이트 늘린다. 늘어난 영역의 메모리 주소를 돌려준다.

        세그먼트 내용(.data + .bss 를 0 으로 채운 것)을 파일 끝에 새로 붙이고 프로그램 헤더가
        그쪽을 가리키게 한다. 원래 자리와 섹션 헤더, 재배치 정보는 그대로 둔다.
        """
        seg = self.segments[index]
        if index != len(self.segments) - 1:
            raise ValueError('마지막 세그먼트만 늘릴 수 있습니다')
        body = bytes(self.data[seg.offset:seg.offset + seg.filesz])
        ext_vaddr = align(seg.vaddr + seg.memsz, seg.align)
        new_offset = align(len(self.data), seg.align)
        new_size = ext_vaddr - seg.vaddr + extra

        self.data += bytes(new_offset - len(self.data))
        self.data += body + bytes(new_size - len(body))
        seg.offset = new_offset
        seg.filesz = seg.memsz = new_size
        self.data[seg.ph_offset:seg.ph_offset + 32] = seg.pack()
        return LOAD_ADDR + ext_vaddr
