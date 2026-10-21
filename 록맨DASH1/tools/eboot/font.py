"""한글 글꼴 텍스처와 문자 테이블 만들기.

chars.txt 의 n 번째 글자가 글자 번호 n 이다. 글자 번호 0x372 부터는 제어 코드(0x372~0x3FF)를
건너뛰어 문자 코드 0x400 부터 쓴다. '★' 는 빈 칸.

텍스처는 4bpp(값 0~3, 원본 글꼴 CLUT 를 그대로 씀) 512x512 이고,
12x12 글자를 한 줄에 41개씩 놓는다. (asm 의 KOR_FONT_* 와 같아야 하며 layout.asm 으로 넘겨준다)
"""
from PIL import Image

COLUMNS = 41
CELL = 12
TEX_SIZE = 512
EMPTY = '★'

CTRL_FIRST = 0x372
EXT_FIRST = 0x400

# fonts.png 의 색 → 4bpp 값 (그 밖의 색은 투명)
PALETTE = {
    (181, 181, 181, 255): 1,
    (99, 99, 99, 255): 2,
    (49, 49, 49, 255): 3,
}
GLYPH_COLUMNS = 20  # fonts.png 한 줄의 글자 수


def glyph_code(index):
    return index if index < CTRL_FIRST else index - CTRL_FIRST + EXT_FIRST


def load_chars(path):
    with open(path, encoding='utf-8') as f:
        chars = f.read().strip()
    if len(chars) > (TEX_SIZE // CELL) * COLUMNS:
        raise ValueError('글자가 너무 많습니다: {}개'.format(len(chars)))
    return chars


def char_table(chars):
    """문자 → 문자 코드. 같은 글자가 여러 번 있으면 뒤의 것을 쓴다."""
    return {ch: glyph_code(i) for i, ch in enumerate(chars) if ch != EMPTY}


def write_tbl(chars, path):
    """DAT 대사 삽입(DashEditor)용 테이블. 형식: 코드(리틀 엔디언 hex)=문자"""
    with open(path, 'w', encoding='utf-8') as f:
        for i, ch in enumerate(chars):
            if ch != EMPTY:
                code = glyph_code(i)
                f.write('{:02X}{:02X}={}\n'.format(code & 0xFF, code >> 8, ch))


def render(chars, glyph_png, glyph_map):
    """(텍스처 바이트, 미리보기 이미지)"""
    with open(glyph_map, encoding='utf-8') as f:
        source = {ch: i for i, ch in enumerate(f.read().replace('\n', ''))}
    glyphs = Image.open(glyph_png).convert('RGBA')

    pixels = bytearray(TEX_SIZE * TEX_SIZE)
    missing = []
    for i, ch in enumerate(chars):
        if ch == EMPTY:
            continue
        if ch not in source:
            missing.append(ch)
            continue
        sx = source[ch] % GLYPH_COLUMNS * CELL
        sy = source[ch] // GLYPH_COLUMNS * CELL
        dx = i % COLUMNS * CELL
        dy = i // COLUMNS * CELL
        for y in range(CELL):
            for x in range(CELL):
                pixels[(dy + y) * TEX_SIZE + dx + x] = PALETTE.get(glyphs.getpixel((sx + x, sy + y)), 0)
    if missing:
        raise ValueError('fonts.png 에 없는 글자: ' + ''.join(missing))

    texture = bytes(pixels[i] | pixels[i + 1] << 4 for i in range(0, len(pixels), 2))

    colors = [(0, 0, 0, 0)] * 4
    for rgba, value in PALETTE.items():
        colors[value] = rgba
    preview = Image.new('RGBA', (TEX_SIZE, TEX_SIZE))
    preview.putdata([colors[p] for p in pixels])
    return texture, preview
