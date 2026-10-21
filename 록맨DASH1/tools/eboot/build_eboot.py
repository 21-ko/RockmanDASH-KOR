"""원본 BOOT.BIN(복호화된 실행파일)으로 한글 EBOOT.BIN 만들기.

  1. .data 세그먼트 뒤에 확장 영역을 붙인다: [asm 코드][한글 글꼴 텍스처][실행파일 대사]
  2. 글꼴 텍스처, 대사(포인터 테이블 수정), 고정 문구, 세이브 화면 문구를 넣는다
  3. armips 로 asm/hangul.asm 을 적용한다 (주소는 layout.asm 으로 넘김)
"""
import os
import re
import shutil
import struct
import subprocess

import exetext
import font
from prx import Prx, align

DATA_SEGMENT = 1
CODE_SIZE = 0x400
TEX_ALIGN = 0x40


class EbootError(Exception):
    pass


def _entries(path):
    """# 주석과 빈 줄을 뺀 줄을 탭으로 나눈다."""
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line and not line.startswith('#'):
                yield line.split('\t')


def put_savedata_text(prx, original, path):
    """.rodata 의 UTF-8 문자열을 바꾼다. 원래 자리(뒤의 0 패딩 포함) 안에 들어가야 한다."""
    for addr, text in _entries(path):
        addr = int(addr, 16)
        text = re.sub(r'\\([n\\])', lambda m: '\n' if m.group(1) == 'n' else '\\', text)
        if original.read(addr - 1, 1) != b'\0':
            raise EbootError('{}: 0x{:08X} 은 문자열 시작이 아닙니다'.format(os.path.basename(path), addr))
        end = original.file_offset(addr)
        while original.data[end]:
            end += 1
        while not original.data[end]:
            end += 1
        size = end - original.file_offset(addr)
        data = text.encode('utf-8')
        if len(data) >= size:
            raise EbootError('{}: 0x{:08X} 문자열이 {}바이트 넘침'.format(
                os.path.basename(path), addr, len(data) + 1 - size))
        prx.write(addr, data + bytes(size - len(data)))


def put_fixed_text(prx, table, path):
    """.data 의 고정 길이 문구 (남는 칸은 전각 공백)."""
    for addr, count, text in _entries(path):
        count = int(count)
        if len(text) > count:
            raise EbootError('{}: "{}" 는 {}글자까지'.format(os.path.basename(path), text, count))
        text = text.ljust(count, '　')
        prx.write(int(addr, 16), struct.pack('<{}H'.format(count), *(table[ch] for ch in text)))


def run_armips(prx, work, asm_path, layout):
    eboot = os.path.join(work, 'EBOOT.BIN')
    with open(eboot, 'wb') as f:
        f.write(prx.data)
    with open(os.path.join(work, 'layout.asm'), 'w', encoding='utf-8') as f:
        f.write('; build_eboot.py 가 만든 파일\n')
        for name, value in layout.items():
            f.write('{:<20} equ 0x{:X}\n'.format(name, value))
    shutil.copy(asm_path, work)
    res = subprocess.run(['armips', os.path.basename(asm_path)], cwd=work)
    if res.returncode != 0:
        raise EbootError('armips 실패')
    with open(eboot, 'rb') as f:
        return f.read()


def _changed_words(a, b, chunk=0x1000):
    for base in range(0, len(a), chunk):
        if a[base:base + chunk] != b[base:base + chunk]:
            for off in range(base, min(base + chunk, len(a)), 4):
                if a[off:off + 4] != b[off:off + 4]:
                    yield off


def check_patch(prx, patched, allowed):
    """asm 이 고친 곳이 allowed(메모리 주소 범위) 안이고 재배치가 걸린 워드가 아닌지 확인."""
    if len(patched) != len(prx.data):
        raise EbootError('armips 가 파일 크기를 바꿨습니다')
    for off in _changed_words(prx.data, patched):
        addr = next((seg.addr + off - seg.offset for seg in prx.segments
                     if seg.offset <= off < seg.offset + seg.filesz), None)
        if addr is None or not any(lo <= addr < hi for lo, hi in allowed):
            raise EbootError('asm 이 허용되지 않은 곳을 고침: 파일 오프셋 0x{:X}'.format(off))
        if addr in prx.relocs:
            raise EbootError('asm 이 재배치되는 워드를 고침: 0x{:08X}'.format(addr))


def build(boot_bin, src, work):
    """src = src/eboot, work = 작업 폴더. (EBOOT.BIN 경로, table.tbl 경로)"""
    os.makedirs(work, exist_ok=True)
    original = Prx(boot_bin)
    prx = Prx(boot_bin)
    assets = os.path.join(src, 'fontassets')
    scripts = os.path.join(src, 'scripts')

    # 글꼴
    chars = font.load_chars(os.path.join(assets, 'chars.txt'))
    table = font.char_table(chars)
    table_path = os.path.join(work, 'table.tbl')
    font.write_tbl(chars, table_path)
    texture, preview = font.render(chars, os.path.join(assets, 'fonts.png'), os.path.join(assets, 'fonts.utf8'))
    preview.save(os.path.join(work, 'font.png'))

    # 대사
    encoded = exetext.encode_all(scripts, table)
    text_size = sum(len(b) for *_, blocks in encoded for b in blocks)

    # 확장 영역
    tex_off = align(CODE_SIZE, TEX_ALIGN)
    text_off = tex_off + len(texture)
    ext = prx.extend_segment(DATA_SEGMENT, text_off + text_size)
    data_seg = prx.segments[DATA_SEGMENT]
    prx.write(ext + tex_off, texture)
    prx.write(ext + text_off, exetext.insert(encoded, prx, data_seg.addr, ext + text_off))

    put_fixed_text(prx, table, os.path.join(scripts, 'fixed.txt'))
    put_savedata_text(prx, original, os.path.join(scripts, 'savedata.txt'))

    text_seg = prx.segments[0]
    layout = {
        'TEXT_HEADERSIZE': text_seg.addr - text_seg.offset,
        'EXT_HEADERSIZE': data_seg.addr - data_seg.offset,
        'EXT_CODE': ext,
        'EXT_CODE_END': ext + CODE_SIZE,
        'KOR_FONT_TEX': ext + tex_off,
        'KOR_FONT_TEX_SIZE': font.TEX_SIZE,
        'KOR_FONT_COLUMNS': font.COLUMNS,
        'KOR_FONT_CELL': font.CELL,
        'CHAR_HALF_SPACE': table[' '],
    }
    patched = run_armips(prx, work, os.path.join(src, 'asm', 'hangul.asm'), layout)
    check_patch(prx, patched, [(text_seg.addr, text_seg.addr + text_seg.filesz), (ext, ext + CODE_SIZE)])

    print('확장 영역 0x{:08X}~0x{:08X} (코드 0x{:X}, 글꼴 0x{:X}, 대사 0x{:X} 바이트)'.format(
        ext, ext + text_off + text_size, CODE_SIZE, len(texture), text_size))
    return os.path.join(work, 'EBOOT.BIN'), table_path
