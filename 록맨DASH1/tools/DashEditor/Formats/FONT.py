from PIL import Image
from Formats.BIN import bytes_to_uint, ulong_to_bytes

sub_width, sub_height = 128, 32
rgba_pal = [
    (0, 0, 0, 0),           # 0 - Transparent
    (181, 181, 181, 255),   # 1 - Light Gray
    (99, 99, 99, 255),      # 2 - Medium Gray
    (49, 49, 49, 255)       # 3 - Dark Gray
]

def rgba_to_index(rgba):
    for i, color in enumerate(rgba_pal):
        if rgba == color:
            return i
    return 0

def bit_combine(tp1, tp2, size):
    out = [0] * size
    for cnt in range(size):
        out[cnt] = (tp1[cnt] & 0x33333333) | ((tp2[cnt] & 0x33333333) << 2)
    return out

def bit_split(combined):
    tp1 = [0] * len(combined)
    tp2 = [0] * len(combined)
    
    for cnt in range(len(combined)):
        tp1[cnt] = combined[cnt] & 0x33333333
        tp2[cnt] = (combined[cnt] >> 2) & 0x33333333
    
    return tp1, tp2

def do_insert_font(original_font, png_file):
    print("Inserting {}".format(png_file))
    
    img = Image.open(png_file)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    sub_width, sub_height = 128, 32
    cols = img.width // sub_width
    rows = img.height // sub_height
    
    all_pixels = []
    for row in range(rows):
        for col in range(cols):
            # 서브 이미지 추출
            left = col * sub_width
            top = row * sub_height
            right = left + sub_width
            bottom = top + sub_height
            
            sub_image = img.crop((left, top, right, bottom))
            
            # 픽셀 색상 처리
            for y in range(sub_height):
                for x in range(sub_width):
                    rgba = sub_image.getpixel((x, y))
                    index = rgba_to_index(rgba)
                    all_pixels.append(index)

    # 4비트 변환
    values = []
    for i in range(0, len(all_pixels), 8):
        value = 0
        for j in range(8):
            if i + j < len(all_pixels):
                value |= (all_pixels[i + j] & 0xF) << (j * 4)
        values.append(value)

    # 합치기
    half_size = len(values) // 2
    tp1 = values[:half_size]
    tp2 = values[half_size:]
    combined = bit_combine(tp1, tp2, half_size)
    
    with open(original_font, "r+b") as f:
        f.seek(2048)
        for value in combined:
            f.write(value.to_bytes(4, byteorder='little'))

def do_extract_font(font_file):
    print("Extracting {}".format(font_file))
    
    with open(font_file, "rb") as f:
        f.seek(2048)
        data = f.read(32768)

    combined = [int.from_bytes(data[i:i+4], byteorder='little') for i in range(0, len(data), 4)]

    tp1, tp2 = bit_split(combined)

    pixels = []
    for value in tp1 + tp2:
        for shift in range(0, 32, 4):
            pixel_8bit = (value >> shift) & 0xF
            pixels.append(pixel_8bit)

    sub_width, sub_height = 128, 32
    num_sub_images = len(pixels) // (sub_width * sub_height)

    sub_images = []

    for i in range(num_sub_images):
        sub_image = Image.new("RGBA", (sub_width, sub_height))
        sub_image_data = [rgba_pal[pixel] for pixel in pixels[i * sub_width * sub_height:(i + 1) * sub_width * sub_height]]
        sub_image.putdata(sub_image_data)
        sub_images.append(sub_image)

    final_width, final_height = 256, 512
    combined_image = Image.new("RGBA", (final_width, final_height))

    cols = final_width // sub_width
    rows = final_height // sub_height

    for idx, sub_image in enumerate(sub_images):
        x = (idx % cols) * sub_width
        y = (idx // cols) * sub_height
        combined_image.paste(sub_image, (x, y))

    output_image = open(font_file.split(".")[0] + ".png", "wb")
    combined_image.save(output_image)

    print("\nFound font. Extraction complete.")
