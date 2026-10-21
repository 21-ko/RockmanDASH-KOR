"""실행파일 안 대사 (TXT/0x????????.txt) 삽입.

파일 이름의 숫자 = .data 안에서 대사 테이블의 위치. 테이블은
  [2바이트 오프셋 x (블록 수 + 1)][블록 데이터...]   (오프셋은 테이블 시작 기준, 마지막은 끝 위치)
번역이 원래 자리에 들어가면 그대로 쓰고, 안 들어가면 4바이트 모드로 바꾼다.
  원래 자리: [FF FF 00 00][4바이트 오프셋 x (블록 수 + 1)]   데이터: 확장 영역 (16바이트 정렬)
4바이트 모드는 asm 이 처리한다 (MsgEntry).
"""
import os
import re
import struct

EP2_COMMANDS = {
    'FUNC': b'', 'POS': b'\xfb\x06', 'WAIT': b'\xfb\x08', 'VWAIT': b'\xfb\x09',
    'COLOR': b'\xfb\x0a', 'INIT_COLOR': b'\xfb\x0b', 'SEL': b'\xfb\x0f', 'PAGEKEY': b'\xfb\x18',
    'VOICELOAD': b'\xfb\x1a', 'ITEM_NAME': b'\xfb\x20', 'BUTTON': b'\xfb\x22', 'ENDKEY': b'\xfb\x24',
    'SPACE': b'\xfb\x2e', 'LINE': b'\xfc', 'NEXTPAGE': b'\xfd\x00', 'END': b'\xff',
}
EP1_COMMANDS = {'FUNC': b'', 'LINE': b'\xfc', 'END': b'\xff'}

LONG_MARK = b'\xff\xff\x00\x00'
SCREEN_WIDTH = 320


class MsgError(Exception):
    pass


# ---- POS 다시 계산 (구 editpostags.py) ----

def _width(text, widths):
    return sum(widths.get(ch, 12) for ch in re.sub(r'<[^>]+>', '', text.rstrip('\n')))


def _fix_pos(block, pos_tag, widths):
    """마지막 POS 태그의 x(가운데 정렬)와 글자 칸 수를 마지막 대사 줄에 맞춘다."""
    lines = block.split('\n')
    text_line = pos_idx = None
    for i, line in enumerate(lines):
        if pos_tag in line:
            pos_idx = i
        elif not line.startswith('<') and line.strip('\n'):
            text_line = line.rstrip('\n')
    if text_line and pos_idx is not None:
        width = _width(text_line, widths)
        x = '{:04X}'.format(max(0, (SCREEN_WIDTH - width) // 2))
        cells = width if width % 12 == 0 else (width // 12 + 1) * 12
        count = '{:02X}'.format(cells // 12 + 1)
        tag, _, params = lines[pos_idx].partition(' ')
        params = params[:-1]
        lines[pos_idx] = '{} {}{}{}{}>'.format(tag, x, params[4:8], count, params[10:])
    return '\n'.join(lines)


def fix_positions(content, pos_tag, widths):
    blocks = content.split('[BLOCK:')
    if blocks[0].strip('\n') == '':
        blocks = blocks[1:]
    return ''.join(_fix_pos('[BLOCK:' + b, pos_tag, widths) for b in blocks if b.strip('\n'))


# ---- 대사 → 블록 바이트 (구 txt2bin.py) ----

def encode_blocks(content, table, commands, keep_empty, name):
    """[BLOCK:] 마다 바이트. keep_empty=False 면 빈 블록은 버린다 (EP1)."""
    blocks = []
    cur = None if keep_empty else bytearray()
    for line in content.split('\n'):
        if line.startswith('[BLOCK:'):
            if cur is not None and (keep_empty or cur):
                blocks.append(cur)
            cur = bytearray()
            continue
        if cur is None:
            continue
        i = 0
        while i < len(line):
            end = line.find('>', i) if line[i] == '<' else -1
            if end != -1:
                body = line[i + 1:end]
                parts = body.split()
                try:
                    if parts and parts[0] in commands:
                        cur += commands[parts[0]] + bytes.fromhex(' '.join(parts[1:]))
                    else:
                        cur += bytes.fromhex(body)
                except ValueError:
                    raise MsgError('{}: 잘못된 명령 <{}>'.format(name, body))
                i = end + 1
            else:
                if line[i] not in table:
                    raise MsgError("{}: 테이블에 없는 글자 '{}'\n    {}".format(name, line[i], line))
                cur += table[line[i]]
                i += 1
    if cur is not None and (keep_empty or cur):
        blocks.append(cur)
    return [bytes(b) for b in blocks]


def load_scripts(txt_dir, table, commands, keep_empty, pos_files=(), pos_tag=None, widths=None):
    """[(.data 오프셋, 블록들)] 파일 이름 순."""
    result = []
    for name in sorted(os.listdir(txt_dir)):
        if not name.endswith('.txt'):
            continue
        with open(os.path.join(txt_dir, name), encoding='utf-8') as f:
            content = f.read()
        if name in pos_files:
            content = fix_positions(content, pos_tag, widths)
        offset = int(re.search(r'0x[0-9A-Fa-f]+', name).group(0), 16)
        result.append((offset, encode_blocks(content, table, commands, keep_empty, name)))
    return result


# ---- 테이블 쓰기 ----

def _offsets(blocks, first):
    out = []
    pos = first
    for b in blocks:
        out.append(pos)
        pos += len(b)
    return out + [pos]


def insert(prx, original, data_addr, scripts, area_addr, area_end):
    """대사를 넣는다. area_addr~area_end = 4바이트 모드 데이터를 넣을 확장 영역. 쓴 크기를 돌려준다."""
    used = 0
    for offset, blocks in scripts:
        table = data_addr + offset
        first = struct.unpack('<H', original.read(table, 2))[0]
        size = struct.unpack('<H', original.read(table + first - 2, 2))[0]
        data = b''.join(blocks)

        short = (len(blocks) + 1) * 2
        if short + len(data) <= size:
            head = struct.pack('<{}H'.format(len(blocks) + 1), *_offsets(blocks, short))
            prx.write(table, (head + data).ljust(size, b'\0'))
            continue

        used = (used + 15) & ~15
        where = area_addr + used
        if where + len(data) > area_end:
            raise MsgError('0x{:08X}.txt: 확장 영역이 모자랍니다'.format(offset))
        head = LONG_MARK + struct.pack('<{}I'.format(len(blocks) + 1), *_offsets(blocks, where - table))
        if len(head) > size:
            raise MsgError('0x{:08X}.txt: 4바이트 오프셋 테이블({}바이트)이 원래 자리({}바이트)보다 큽니다'.format(
                offset, len(head), size))
        prx.write(table, head.ljust(size, b'\0'))
        prx.write(where, data)
        used += len(data)
    return used
