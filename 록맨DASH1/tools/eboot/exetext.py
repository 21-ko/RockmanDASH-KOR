"""실행파일 안 대사(시스템 문구, 컷신 자막) 삽입.

대사 파일의 [Block] 순서 = 원본 포인터 테이블 값의 크기 순서.
번역 대사는 확장 영역에 차례로 넣고 포인터 테이블(.data)만 새 위치로 바꾼다.
"""
import os
import re
import struct

COMMANDS = {
    'CIRCLE': 0x00FD, 'TRIANGLE': 0x00FE, 'CROSS': 0x00FF, 'SQUARE': 0x0100,
    'L1': 0x0101, 'L2': 0x0102, 'R1': 0x0103, 'R2': 0x0104, 'HAND': 0x0109,
    'CLOSE': 0x0372, 'LINE': 0x0374, 'CLEAR': 0x0375, 'COLOR': 0x0377,
    'PAUSE': 0x0379, 'WIN': 0x037A, 'AUDIO': 0x037D, 'DECOR': 0x0381,
    'MOVE_FREE': 0x0382, 'SEL': 0x0384, 'CALL': 0x0387, 'GET': 0x0388,
    'GIVE': 0x0389, 'MSG_IF': 0x038A, 'SLIDE_WIN': 0x038B, 'NEXT': 0x038D,
    'SPACE': 0x038E, 'NO_CHAR_SFX': 0x038F, 'CHAR_SFX': 0x0390, 'WAIT': 0x0392,
    'CAM': 0x0393, 'END': 0x0397, 'EXE_JUMP': 0x039A, 'OPTION': 0x039C,
    'LINES': 0x039D, 'RESTORE_HP': 0x03A0, 'RESTORE_SP': 0x03A1,
    'RESTORE_SHIELD': 0x03A2, 'IF': 0x03A7, 'COST': 0x03A8, 'JUMP': 0x03AD,
    'GIFT': 0x03B5, 'ZENNY_AMOUNT': 0x03B6, 'PART': 0x03B7, 'ITEM': 0x03BE,
    'PRICE_ZENNY': 0x03C1, 'NO_WIN': 0x03C6,
}

SYSTEM_DIR = 'dataKor'     # 그대로 넣는 대사
SUBTITLE_DIR = 'subtitles'  # 가운데 정렬해서 넣는 자막

# (대사 파일, 포인터 테이블의 .data 오프셋, 테이블 크기)
SCRIPTS = [
    ('.data_type1_1_0xce38.txt', 0xCE38 + 0x28C4 - 0x3E0, 0x3E0),  # 시스템 문구
    ('.data_type2_1_0xfec4.txt', 0xFEC4, 40),
    ('.data_type2_2_0x10390.txt', 0x10390, 80),
    ('.data_type2_3_0x10608.txt', 0x10608, 40),
    ('.data_type2_4_0x10e38.txt', 0x10E38, 136),
    ('.data_type2_5_0x11754.txt', 0x11754, 144),
    ('.data_type2_6_0x11ac0.txt', 0x11AC0, 52),
    ('.data_type2_7_0x11fd4.txt', 0x11FD4, 76),
    ('.data_type2_8_0x120ec.txt', 0x120EC, 12),
    ('.data_type2_9_0x12178.txt', 0x12178, 8),
    ('.data_type1_1_0x12184.txt', 0x12270, 16),
    ('.data_type2_10_0x12340.txt', 0x12340, 12),
    ('.data_type2_11_0x12410.txt', 0x12410, 12),
    ('.data_type2_12_0x124e0.txt', 0x124E0, 12),
    ('.data_type2_13_0x125c4.txt', 0x125C4, 16),
    ('.data_type2_14_0x12c58.txt', 0x12C58, 108),
    ('.data_type2_15_0x12f90.txt', 0x12F90, 48),
    ('.data_type2_16_0x131fc.txt', 0x131FC, 40),
    ('.data_type2_17_0x1350c.txt', 0x1350C, 48),
    ('.data_type2_18_0x1357c.txt', 0x1357C, 4),
    ('.data_type2_19_0x13c30.txt', 0x13C30, 116),
    ('.data_type2_20_0x13d50.txt', 0x13D50, 12),
    ('.data_type2_21_0x141f8.txt', 0x141F8, 76),
    ('.data_type2_22_0x14498.txt', 0x14498, 40),
    ('.data_type2_23_0x14840.txt', 0x14840, 60),
    ('.data_type2_24_0x1493c.txt', 0x1493C, 12),
    ('.data_type2_25_0x14e38.txt', 0x14E38, 80),
    ('.data_type2_26_0x154ac.txt', 0x154AC, 108),
    ('.data_type3_27_0x1551c.txt', 0x1551C + 0xBC - 0x1C, 0x1C),
    ('.data_type3_28_0x155d8.txt', 0x155D8 + 0x110 - 0x20, 0x20),
    ('.data_type2_29_0x15818.txt', 0x15818, 20),
    ('.data_type2_30_0x15ca8.txt', 0x15CA8, 76),
    ('.data_type3_31_0x15cf8.txt', 0x15CF8 + 0x398 - 0x44, 0x44),
    ('.data_type3_32_0x16090.txt', 0x16090 + 0x2C4 - 0x38, 0x38),
    ('.data_type2_33_0x165d8.txt', 0x165D8, 44),
    ('.data_type2_34_0x16d10.txt', 0x16D10, 124),
    ('.data_type2_35_0x17470.txt', 0x17470, 120),
    ('.data_type2_36_0x18008.txt', 0x18008, 184),
    ('.data_type2_37_0x18664.txt', 0x18664, 96),
    ('.data_type2_38_0x18c5c.txt', 0x18C5C, 92),
    ('.data_type2_39_0x18d00.txt', 0x18D00, 4),
    ('.data_type3_40_0x18d08.txt', 0x18D08 + 0x129C - 0x130, 0x130),
    ('.data_type2_41_0x1a478.txt', 0x1A478, 80),
    ('.data_type2_42_0x1a5f4.txt', 0x1A5F4, 20),
    ('.data_type2_43_0x1aa8c.txt', 0x1AA8C, 76),
    ('.data_type2_44_0x1ad58.txt', 0x1AD58, 44),
    ('.data_type2_45_0x1b55c.txt', 0x1B55C, 136),
]

# 첫 블록이 대사가 아니라 포인터 테이블 밖의 데이터인 파일
SKIP_FIRST_BLOCK = {'.data_type1_1_0xce38.txt'}

SUBTITLE_WIDTH = 24 * 12


class ScriptError(Exception):
    pass


# ---- 자막 가운데 정렬 (구 addsubgap.py) ----

def _center(text):
    width = sum(6 if ch == ' ' else 12 for ch in text)
    if width >= SUBTITLE_WIDTH:
        return text
    gap = (SUBTITLE_WIDTH - width) // 2
    return '<SPACE {:02X}{:02X}>'.format(gap & 0xFF, gap >> 8) + text


def center_subtitles(script):
    """태그 사이의 각 대사 앞에 <SPACE> 를 넣어 가운데 정렬한다."""
    tag = re.compile(r'(<.*?>|\[.*?\])', re.S)

    def dialogue(m):
        text = tag.sub('', m.group(0)).strip()
        return m.group(0).replace(text, _center(text)) if text else m.group(0)

    def block(m):
        return m.group(1) + re.sub(r'(.*?)(?=<|\n|$)', dialogue, m.group(2))

    return re.sub(r'(\[Block [0-9A-Fa-f]+, String: [A-F0-9]+-[A-F0-9]+\]\n)(.*?)(?=\[Block|\Z)',
                  block, script, flags=re.S)


# ---- 대사 → 바이너리 ----

def _encode_tag(body):
    parts = body.split()
    if re.fullmatch(r'[0-9A-Fa-f]{4}', parts[0]):
        code = int(parts[0], 16)
    elif parts[0] in COMMANDS:
        code = COMMANDS[parts[0]]
    else:
        raise ScriptError('알 수 없는 명령: <{}>'.format(body))
    return struct.pack('<H', code) + bytes.fromhex(''.join(parts[1:]))


def encode_script(script, table, name):
    """[Block] 마다 인코딩한 바이트 (2바이트 정렬)."""
    blocks = []
    for block in re.split(r'\[Block', script)[1:]:
        lines = block.strip().splitlines()
        if not re.match(r'\w+, String: [0-9A-Fa-f]+-[0-9A-Fa-f]+', lines[0]):
            raise ScriptError('{}: 블록 머리가 잘못됨: [Block{}'.format(name, lines[0]))
        out = bytearray()
        for line in lines[1:]:
            try:
                for part in re.split(r'(<[^>]+>)', line):
                    if part.startswith('<') and part.endswith('>'):
                        out += _encode_tag(part[1:-1])
                    else:
                        for ch in part:
                            if ch not in table:
                                raise ScriptError("테이블에 없는 글자 '{}'".format(ch))
                            out += struct.pack('<H', table[ch])
            except (ScriptError, ValueError) as e:
                raise ScriptError('{}: {}\n    {}'.format(name, e, line.strip()))
        if len(out) % 2:
            out += b'\0'
        blocks.append(bytes(out))
    return blocks


def read_script(script_dir, name):
    path = os.path.join(script_dir, SUBTITLE_DIR, name)
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            return center_subtitles(f.read())
    with open(os.path.join(script_dir, SYSTEM_DIR, name), encoding='utf-8') as f:
        return f.read()


def encode_all(script_dir, table):
    """SCRIPTS 순서대로 [(파일, 테이블 오프셋, 테이블 크기, 블록들)]"""
    result = []
    for name, table_off, table_size in SCRIPTS:
        blocks = encode_script(read_script(script_dir, name), table, name)
        if name in SKIP_FIRST_BLOCK:
            blocks = blocks[1:]
        result.append((name, table_off, table_size, blocks))
    return result


def insert(scripts, prx, data_addr, text_addr):
    """포인터 테이블을 고치고, text_addr 에 넣을 대사 바이트를 돌려준다.

    data_addr: .data 의 메모리 주소
    """
    blob = bytearray()
    for name, table_off, table_size, blocks in scripts:
        # 포인터 값 크기 순서 = 블록 순서 (0, 0xFFFFFFFF 는 빈 칸)
        table_addr = data_addr + table_off
        values = struct.unpack('<{}I'.format(table_size // 4), prx.read(table_addr, table_size))
        slots = sorted((i for i, v in enumerate(values) if v not in (0, 0xFFFFFFFF)),
                       key=lambda i: values[i])
        if len(blocks) != len(slots):
            raise ScriptError('{}: 블록 {}개, 포인터 {}개'.format(name, len(blocks), len(slots)))

        for slot, data in zip(slots, blocks):
            at = table_addr + slot * 4
            prx.write(at, struct.pack('<I', prx.pointer_value(at, text_addr + len(blob))))
            blob += data
    return bytes(blob)
