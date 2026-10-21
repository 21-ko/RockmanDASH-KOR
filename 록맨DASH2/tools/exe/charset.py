"""글자 테이블(Moji.tbl)과 EP2 한글 글꼴 텍스처.

EP2 (chars.txt 의 n 번째 글자 = 글자 번호 n)
  - 문자 코드: 0x00~0xE9 는 1바이트, 그 뒤는 2바이트 0xF100~0xF6CF (평면 1), 0xF700~ (평면 2)
  - 글꼴: 4bpp 텍스처 한 장(1024x512)에 2비트 평면 두 개. 평면마다 12x12 글자를 한 줄에 41개, 1722자.
    평면 1 = 글자 번호 0~1721, 평면 2 = 1722~. 어느 평면을 보일지는 CLUT 로 고른다.
  - 테이블에서 끝의 '”', '★' 는 뺀다 (끝의 ” 는 실행파일이 직접 찍는 2바이트 ”).
EP1
  - 원본 테이블(Moji_pre.tbl) 뒤에 한글(chars_onlykor.txt)을 0xF828 부터 붙인다. 글꼴은 DAT(INIT.BIN) 쪽.
"""
from PIL import Image

CELL = 12
COLUMNS = 41
PLANE_GLYPHS = 1722            # 평면 하나에 들어가는 글자 수 (41 x 42)
TEX_WIDTH, TEX_HEIGHT = 1024, 512

ONE_BYTE_COUNT = 0xEA          # 1바이트 문자 코드 개수
TWO_BYTE_FIRST = 0xF100        # 평면 1 의 첫 2바이트 코드 (글자 번호 0xEA)
PLANE2_FIRST = 0xF700          # 평면 2 의 첫 코드 (글자 번호 PLANE_GLYPHS)

GLYPH_PNG_COLUMNS = 20         # fonts.png 한 줄의 글자 수
PALETTE = {
    (225, 216, 208, 255): 1,
    (146, 144, 152, 255): 2,
    (75, 80, 96, 255): 3,
}


class CharsetError(Exception):
    pass


def ep2_code(index):
    if index < ONE_BYTE_COUNT:
        return index
    if index < PLANE_GLYPHS:
        return TWO_BYTE_FIRST - ONE_BYTE_COUNT + index
    return PLANE2_FIRST + index - PLANE_GLYPHS


def code_bytes(code):
    """문자 코드 → 대사에 들어가는 바이트 (2바이트 코드는 큰 쪽 먼저)."""
    return bytes([code]) if code < 0x100 else bytes([code >> 8, code & 0xFF])


def read_text(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def ep2_table_lines(chars):
    lines = []
    for i, ch in enumerate(chars.rstrip('”★')):
        code = ep2_code(i)
        lines.append('{:02X}={}'.format(code, ch) if code < 0x100 else '{:04X}={}'.format(code, ch))
    return lines + ['4E=∼', '4E=~']


def ep1_table_lines(pre_table, kor_chars):
    """원본 테이블 줄 + 빈 줄 + 한글 (0xF828~, 0xF8B4~0xF8FF, 0xF9DC~0xF9FF 는 건너뜀)."""
    lines = pre_table.split('\n')
    code = 0xF828
    for ch in kor_chars.strip('★'):
        if code == 0xF8B4:
            code = 0xF900
        if code == 0xF9DC:
            code = 0xFA00
        lines.append('{:04X}={}'.format(code, ch))
        code += 1
    return lines


def write_table(lines, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def parse_table(lines):
    """문자 → 바이트. 같은 문자가 여러 번 있으면 뒤의 것."""
    table = {}
    for line in lines:
        if line:
            code, ch = line.split('=', 1)
            table[ch] = bytes.fromhex(code)
    return table


def _glyph_source(glyph_png, glyph_map):
    with open(glyph_map, encoding='utf-8') as f:
        index = {ch: i for i, ch in enumerate(f.read().replace('\n', ''))}
    return Image.open(glyph_png).convert('RGBA'), index


def ep2_texture(chars, glyph_png, glyph_map):
    """(4bpp 텍스처 바이트, 미리보기 이미지 2장)"""
    glyphs, source = _glyph_source(glyph_png, glyph_map)
    missing = sorted(set(ch for ch in chars if ch not in source))
    if missing:
        raise CharsetError('fonts.png 에 없는 글자: ' + ''.join(missing))
    planes = [bytearray(TEX_WIDTH * TEX_HEIGHT) for _ in range(2)]
    for i, ch in enumerate(chars):
        plane, pos = divmod(i, PLANE_GLYPHS)
        if plane > 1:
            raise CharsetError('글자가 너무 많습니다: {}개'.format(len(chars)))
        sx = source[ch] % GLYPH_PNG_COLUMNS * CELL
        sy = source[ch] // GLYPH_PNG_COLUMNS * CELL
        dx = pos % COLUMNS * CELL
        dy = pos // COLUMNS * CELL
        for y in range(CELL):
            for x in range(CELL):
                planes[plane][(dy + y) * TEX_WIDTH + dx + x] = PALETTE.get(glyphs.getpixel((sx + x, sy + y)), 0)

    nibbles = [a | b << 2 for a, b in zip(*planes)]
    texture = bytes(nibbles[i] | nibbles[i + 1] << 4 for i in range(0, len(nibbles), 2))

    colors = [(0, 0, 0, 0)] * 4
    for rgba, value in PALETTE.items():
        colors[value] = rgba
    previews = []
    for plane in planes:
        img = Image.new('RGBA', (TEX_WIDTH, TEX_HEIGHT))
        img.putdata([colors[p] for p in plane])
        previews.append(img)
    return texture, previews
