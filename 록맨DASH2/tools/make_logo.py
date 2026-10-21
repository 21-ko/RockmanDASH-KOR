"""EP2 로고 이미지 → 타이틀 텍스처 소스, PIC1.PNG, ICON0.PNG (한 번 실행해서 결과를 src 에 넣는다).

1. 타이틀 (COMMON/TITLE.BIN): 8bpp 텍스처 4조각 (가로 480, 세로 68+68+68+20 = 224).
   256색 CLUT 는 0001_TITLE.PIX 앞 0x200 바이트. 원본처럼 245색 + 투명 11칸, 색에는 STP 비트를 켠다.
   입력의 바깥 틀은 버리고 어두운 로고 판만 원본 판 자리(4,0)-(476,218)에 비율 유지로 가운데 맞춘다.
   → src/ep2/tex/BMP/0001~0004_TITLE.PNG (팔레트 색 그대로), src/ep2/tex/ORG/TITLE01_LOGO.CLT
2. PIC1.PNG, ICON0.PNG: 원본 ISO 의 그림에서 로고 자리(틀 포함)에 틀 포함 로고를 그대로 줄여 넣는다.
   ICON0 은 마스코트 손이 로고 앞에 있어서 그 픽셀은 원본을 다시 덮는다.
   → src/iso/PIC1.PNG, src/iso/ICON0.PNG (빌드가 ICON0 을 savepic.png 에도 넣는다)

사용: python tools/make_logo.py <로고.png>
"""
import io
import os
import struct
import sys

from PIL import Image

from isotool import IsoImage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
ORIGINAL_ISO = os.path.join(ROOT, '원본', 'UMD9660.ISO')

TITLE_WIDTH = 480
TITLE_STRIPS = [('0001_TITLE.PNG', 68), ('0002_TITLE.PNG', 68), ('0003_TITLE.PNG', 68), ('0004_TITLE.PNG', 20)]
TITLE_SLOT = (4, 0, 476, 218)     # 원본 로고 판 (불투명 영역)
N_COLORS = 245
DARK = 45                         # 로고 판 배경으로 볼 밝기 (RGB 최댓값)

PIC1_BOX = (361, 21, 477, 75)     # 원본 PIC1 의 로고 (틀 포함)
ICON0_BOX = (39, 4, 141, 52)      # 원본 ICON0 의 로고 (틀 포함)
ICON0_MASCOT = [(45, 44), (32, 40)]  # 마스코트 손, 얼굴 안의 점
ICON0_MASCOT_AREA = (28, 28, 57, 61)


def panel_box(img):
    """가운데 줄/칸에서 바깥 틀 안쪽의 어두운 판 범위."""
    w, h = img.size
    dark = lambda p: max(p) < DARK
    row = [img.getpixel((x, h // 2)) for x in range(w)]
    col = [img.getpixel((w // 2, y)) for y in range(h)]
    left = next(x for x in range(w) if dark(row[x]))
    right = next(x for x in range(w - 1, -1, -1) if dark(row[x]))
    top = next(y for y in range(h) if dark(col[y]))
    bottom = next(y for y in range(h - 1, -1, -1) if dark(col[y]))
    return left, top, right + 1, bottom + 1


def to5551(rgb):
    r, g, b = (v >> 3 for v in rgb)
    return 0x8000 | b << 10 | g << 5 | r


def from5551(c):
    """tools/ep2/ImageHill.readCLUT 과 같은 변환."""
    return (c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3, 255


def make_title(logo):
    box = panel_box(logo)
    panel = logo.crop(box)
    sw, sh = TITLE_SLOT[2] - TITLE_SLOT[0], TITLE_SLOT[3] - TITLE_SLOT[1]
    scale = min(sw / panel.width, sh / panel.height)
    size = (round(panel.width * scale), round(panel.height * scale))
    panel = panel.resize(size, Image.LANCZOS).point(lambda v: v >> 3 << 3)
    pos = (TITLE_SLOT[0] + (sw - size[0]) // 2, TITLE_SLOT[1] + (sh - size[1]) // 2)

    indexed = panel.quantize(colors=N_COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = indexed.getpalette()[:N_COLORS * 3]
    clut = [to5551(pal[i * 3:i * 3 + 3]) for i in range(N_COLORS)] + [0] * (256 - N_COLORS)
    colors = [from5551(c) for c in clut[:N_COLORS]]

    image = Image.new('RGBA', (TITLE_WIDTH, sum(h for _, h in TITLE_STRIPS)), (0, 0, 0, 0))
    body = Image.new('RGBA', size)
    body.putdata([colors[i] for i in indexed.getdata()])
    image.paste(body, pos)

    tex = os.path.join(SRC, 'ep2', 'tex')
    y = 0
    for name, h in TITLE_STRIPS:
        image.crop((0, y, TITLE_WIDTH, y + h)).save(os.path.join(tex, 'BMP', name))
        y += h
    with open(os.path.join(tex, 'ORG', 'TITLE01_LOGO.CLT'), 'wb') as f:
        f.write(struct.pack('<256H', *clut))
    print('타이틀: 로고 판 {} → {} 크기 {}, {}색'.format(box, pos, size, len(set(indexed.getdata()))))


def mascot_mask(img):
    """ICON0 에서 로고 앞에 있는 마스코트 픽셀 (피부색·갈색 외곽선, 그 바로 옆 어두운 외곽선)."""
    def mascot(p):
        r, g, b = p
        return r >= b + 15 and (b >= 0.4 * r or g <= 0.6 * r)

    x0, y0, x1, y1 = ICON0_MASCOT_AREA
    seen = set()
    stack = list(ICON0_MASCOT)
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (x0 <= x < x1 and y0 <= y < y1) or not mascot(img.getpixel((x, y))):
            continue
        seen.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    edge = {(x + dx, y + dy) for x, y in seen for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    return seen | {p for p in edge - seen if max(img.getpixel(p)) < 64}


def paste_logo(base, logo, box, keep=()):
    out = base.copy()
    out.paste(logo.resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS), box[:2])
    for p in keep:
        if box[0] <= p[0] < box[2] and box[1] <= p[1] < box[3]:
            out.putpixel(p, base.getpixel(p))
    return out


def make_iso_images(logo):
    iso = IsoImage(ORIGINAL_ISO, writable=False)
    try:
        pic1 = Image.open(io.BytesIO(iso.read('PSP_GAME/PIC1.PNG'))).convert('RGB')
        icon0 = Image.open(io.BytesIO(iso.read('PSP_GAME/ICON0.PNG'))).convert('RGB')
    finally:
        iso.close()
    paste_logo(pic1, logo, PIC1_BOX).save(os.path.join(SRC, 'iso', 'PIC1.PNG'), optimize=True)
    mask = mascot_mask(icon0)
    paste_logo(icon0, logo, ICON0_BOX, mask).save(os.path.join(SRC, 'iso', 'ICON0.PNG'), optimize=True)
    print('PIC1: 로고 {}, ICON0: 로고 {} (마스코트 {}픽셀 유지)'.format(PIC1_BOX, ICON0_BOX, len(mask)))


def main(path):
    logo = Image.open(path).convert('RGB')
    make_title(logo)
    make_iso_images(logo)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
