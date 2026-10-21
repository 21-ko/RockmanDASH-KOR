"""원본 실행파일로 한글 실행파일 만들기.

  EP2: src/ep2/exe/BOOT.BIN   → EBOOT.BIN   (글꼴 텍스처, 대사, 고정 문구, 세이브 문구, asm)
  EP1: src/ep1/exe/dash2e1.prx → dash2e1.prx (대사, asm)

각 실행파일의 .data 세그먼트 뒤에 확장 영역을 붙인다.
  EP2: [asm 코드][글꼴 텍스처][4바이트 모드 대사]   EP1: [asm 코드][4바이트 모드 대사]
확장 영역의 끝은 배포본과 같은 주소로 고정한다. dash2e1.prx 는 EBOOT 바로 뒤(0x091B2000)에
올라가는데 EP1 asm 이 그 주소를 쓰기 때문이다.
"""
import os
import re
import shutil
import struct
import subprocess

import charset
import msgtext
from prx import Prx, align

DATA_SEGMENT = 1
TEX_ALIGN = 0x40

EBOOT_END = 0x091ADF90          # EBOOT 메모리 끝 (배포본과 같음)
EBOOT_CODE_SIZE = 0x800
EP1_LOAD_ADDR = 0x091B2000      # dash2e1.prx 가 올라가는 주소 (EBOOT_END 뒤)
PRX_END = EP1_LOAD_ADDR + 0x54ED90  # dash2e1.prx 메모리 끝 (배포본과 같음)
PRX_CODE_SIZE = 0x200


class ExeError(Exception):
    pass


def _entries(path):
    """# 주석과 빈 줄을 뺀 줄을 탭으로 나눈다."""
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if line and not line.startswith('#'):
                yield line.split('\t')


def put_savedata_text(prx, original, path):
    """UTF-8 문자열을 바꾼다. 원래 문자열(+끝의 0) 뒤 4바이트 경계까지 쓸 수 있다."""
    name = os.path.basename(path)
    for addrs, text in _entries(path):
        data = re.sub(r'\\([nr\\])', lambda m: {'n': '\n', 'r': '\r', '\\': '\\'}[m.group(1)], text).encode('utf-8')
        for addr in (int(a, 16) for a in addrs.split(',')):
            if original.read(addr - 1, 1) != b'\0':
                raise ExeError('{}: 0x{:08X} 은 문자열 시작이 아닙니다'.format(name, addr))
            size = align(addr + original.read(addr, 0x400).index(b'\0') + 1, 4) - addr
            if len(data) >= size:
                raise ExeError('{}: 0x{:08X} 문자열이 {}바이트 넘침'.format(name, addr, len(data) + 1 - size))
            prx.write(addr, data.ljust(size, b'\0'))


def put_fixed_text(prx, table, path):
    """고정 길이 문구. 글자마다 u16 코드, 남는 칸은 전각 공백."""
    for addr, count, text in _entries(path):
        count = int(count)
        if len(text) > count:
            raise ExeError('{}: "{}" 는 {}글자까지'.format(os.path.basename(path), text, count))
        codes = [int.from_bytes(table[ch], 'big') for ch in text.ljust(count, '　')]
        prx.write(int(addr, 16), struct.pack('<{}H'.format(count), *codes))


def read_list(path):
    with open(path, encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip()}


def run_armips(prx, work, out_name, asm_files, layout):
    out = os.path.join(work, out_name)
    with open(out, 'wb') as f:
        f.write(prx.data)
    with open(os.path.join(work, 'layout.asm'), 'w', encoding='utf-8') as f:
        f.write('; build_exe.py 가 만든 파일\n')
        for name, value in layout.items():
            f.write('{:<20} equ 0x{:X}\n'.format(name, value))
    for path in asm_files:
        shutil.copy(path, work)
    res = subprocess.run(['armips', os.path.basename(asm_files[0])], cwd=work)
    if res.returncode != 0:
        raise ExeError('armips 실패')
    with open(out, 'rb') as f:
        return f.read()


def _changed_words(a, b, chunk=0x1000):
    for base in range(0, len(a), chunk):
        if a[base:base + chunk] != b[base:base + chunk]:
            for off in range(base, min(base + chunk, len(a)), 4):
                if a[off:off + 4] != b[off:off + 4]:
                    yield off


def check_patch(prx, patched):
    """asm 이 실행파일 세그먼트 밖이나 재배치가 걸린 워드를 고치지 않았는지 확인."""
    if len(patched) != len(prx.data):
        raise ExeError('armips 가 파일 크기를 바꿨습니다')
    for off in _changed_words(prx.data, patched):
        addr = next((seg.addr + off - seg.offset for seg in prx.segments
                     if seg.offset <= off < seg.offset + seg.filesz), None)
        if addr is None:
            raise ExeError('asm 이 세그먼트 밖을 고침: 파일 오프셋 0x{:X}'.format(off))
        if addr in prx.relocs:
            raise ExeError('asm 이 재배치되는 워드를 고침: 0x{:08X}'.format(addr))


def _layout(prx, ext, code_size):
    text_seg, data_seg = prx.segments
    return {
        'TEXT_HEADERSIZE': text_seg.addr - text_seg.offset,
        'DATA_HEADERSIZE': data_seg.addr - data_seg.offset,
        'EXT_CODE': ext,
        'EXT_CODE_END': ext + code_size,
    }


def _ep2_constants(chars, table):
    """asm 이 쓰는 글자 코드와 글꼴 위치."""
    def code(ch):
        return int.from_bytes(table[ch], 'big')

    def cell(ch):
        i = chars.index(ch)
        if i >= charset.ONE_BYTE_COUNT:
            raise ExeError("커서 글자 '{}' 는 1바이트 글자여야 합니다".format(ch))
        return i % charset.COLUMNS, i // charset.COLUMNS

    buttons = [code(ch) for ch in '○△▽□']
    if buttons != list(range(buttons[0], buttons[0] + 4)):
        raise ExeError('버튼 글자 ○△▽□ 는 chars.txt 에 연달아 있어야 합니다')
    (open_col, open_row), (fill_col, fill_row) = cell('▷'), cell('▶')
    if open_row != fill_row:
        raise ExeError('▷ ▶ 는 글꼴의 같은 줄에 있어야 합니다')
    base = charset.TWO_BYTE_FIRST - charset.ONE_BYTE_COUNT
    return {
        'ONE_BYTE_COUNT': charset.ONE_BYTE_COUNT,
        'KOR_LEAD_FIRST': charset.TWO_BYTE_FIRST >> 8,
        'KOR_PLANE2_LEAD': charset.PLANE2_FIRST >> 8,
        'KOR_CODE_BASE': base,
        'KOR_PLANE2_INDEX': charset.PLANE2_FIRST - base,
        'KOR_FONT_COLUMNS': charset.COLUMNS,
        'BUTTON_FIRST': buttons[0],
        'CURSOR_OPEN_COL': open_col,
        'CURSOR_FILL_COL': fill_col,
        'CURSOR_ROW': open_row,
        'CLOSE_QUOTE': charset.ep2_code(chars.rindex('”')),
        'CODE_SA': code('사'),
        'CODE_MOT': code('못'),
        'CODE_FULL_SPACE': code('　'),
    }


def load_widths(path, chars):
    widths = {}
    for ch, width in _entries(path):
        ch = ' ' if ch == 'SPACE' else ch
        if chars.find(ch) not in range(charset.ONE_BYTE_COUNT):
            raise ExeError("widths.txt: '{}' 는 1바이트 글자가 아닙니다".format(ch))
        widths[ch] = int(width)
    return widths


def build_ep2(boot, src, work):
    """src = src/ep2/exe. (EBOOT.BIN 경로, Moji.tbl 경로, .data 의 파일 오프셋)"""
    os.makedirs(work, exist_ok=True)
    original = Prx(boot)
    prx = Prx(boot)
    data_dir = os.path.join(src, 'DATA')

    raw_chars = charset.read_text(os.path.join(data_dir, 'chars.txt'))
    chars = raw_chars.strip()
    table_lines = charset.ep2_table_lines(raw_chars)
    table_path = os.path.join(work, 'Moji.tbl')
    charset.write_table(table_lines, table_path)
    table = charset.parse_table(table_lines)
    widths = load_widths(os.path.join(data_dir, 'widths.txt'), chars)
    texture, previews = charset.ep2_texture(chars, os.path.join(data_dir, 'fonts.png'),
                                            os.path.join(data_dir, 'fonts.utf8'))
    for i, img in enumerate(previews, 1):
        img.save(os.path.join(work, 'font{}.png'.format(i)))
    scripts = msgtext.load_scripts(os.path.join(src, 'TXT'), table, msgtext.EP2_COMMANDS, keep_empty=True,
                                   pos_files=read_list(os.path.join(data_dir, 'list.txt')),
                                   pos_tag='<POS', widths=widths)

    ext = prx.extend_segment_to(DATA_SEGMENT, EBOOT_END)
    data_seg = prx.segments[DATA_SEGMENT]
    font_addr = align(ext + EBOOT_CODE_SIZE, TEX_ALIGN)
    text_addr = font_addr + len(texture)
    prx.write(font_addr, texture)
    used = msgtext.insert(prx, original, data_seg.addr, scripts, text_addr, EBOOT_END)
    put_fixed_text(prx, table, os.path.join(src, 'fixed.txt'))
    put_savedata_text(prx, original, os.path.join(src, 'savedata.txt'))

    with open(os.path.join(work, 'widths.bin'), 'wb') as f:
        f.write(bytes(widths.get(ch, 12) for ch in chars[:charset.ONE_BYTE_COUNT]))
    layout = _layout(prx, ext, EBOOT_CODE_SIZE)
    layout.update(KOR_FONT_TEX=font_addr, KOR_FONT_TEX_SIZE=512, **_ep2_constants(chars, table))
    patched = run_armips(prx, work, 'EBOOT.BIN',
                         [os.path.join(src, 'hangul.asm'), os.path.join(src, '..', '..', 'msgtable.asm')],
                         layout)
    check_patch(prx, patched)
    print('EBOOT 확장 영역 0x{:08X}~0x{:08X}: 코드 0x{:X}, 글꼴 0x{:X}, 대사 0x{:X} / 0x{:X} 바이트'.format(
        ext, EBOOT_END, EBOOT_CODE_SIZE, len(texture), used, EBOOT_END - text_addr))
    return os.path.join(work, 'EBOOT.BIN'), table_path, data_seg.offset


def build_ep1(prx_bin, src, work):
    """src = src/ep1/exe. (dash2e1.prx 경로, Moji.tbl 경로, .data 의 파일 오프셋)"""
    os.makedirs(work, exist_ok=True)
    original = Prx(prx_bin, EP1_LOAD_ADDR)
    prx = Prx(prx_bin, EP1_LOAD_ADDR)
    data_dir = os.path.join(src, 'DATA')

    table_lines = charset.ep1_table_lines(charset.read_text(os.path.join(data_dir, 'Moji_pre.tbl')),
                                         charset.read_text(os.path.join(data_dir, 'chars_onlykor.txt')))
    table_path = os.path.join(work, 'Moji.tbl')
    charset.write_table(table_lines, table_path)
    table = charset.parse_table(table_lines)
    scripts = msgtext.load_scripts(os.path.join(src, 'TXT'), table, msgtext.EP1_COMMANDS, keep_empty=False,
                                   pos_files=read_list(os.path.join(data_dir, 'list.txt')),
                                   pos_tag='<FB06', widths={' ': 6})

    ext = prx.extend_segment_to(DATA_SEGMENT, PRX_END)
    data_seg = prx.segments[DATA_SEGMENT]
    text_addr = ext + PRX_CODE_SIZE
    used = msgtext.insert(prx, original, data_seg.addr, scripts, text_addr, PRX_END)

    patched = run_armips(prx, work, 'dash2e1.prx',
                         [os.path.join(src, 'hangul.asm'), os.path.join(src, '..', '..', 'msgtable.asm')],
                         _layout(prx, ext, PRX_CODE_SIZE))
    check_patch(prx, patched)
    print('prx 확장 영역 0x{:08X}~0x{:08X}: 코드 0x{:X}, 대사 0x{:X} / 0x{:X} 바이트'.format(
        ext, PRX_END, PRX_CODE_SIZE, used, PRX_END - text_addr))
    return os.path.join(work, 'dash2e1.prx'), table_path, data_seg.offset
