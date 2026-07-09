from PIL import Image
import random
import os

SIZE = 16
OUT_DIR = '/Users/s13010282/Documents/pythonのやつ/m/textures'

os.makedirs(OUT_DIR, exist_ok=True)

TEXTURES = {
    'dirt.png':  [(101, 67, 33), (120, 80, 40), (85, 55, 25)],
    'stone.png': [(120, 120, 120), (140, 140, 140), (100, 100, 100)],
    'wood.png':  [(90, 60, 30), (110, 75, 40), (70, 45, 20)],
    'leaf.png':  [(40, 120, 40), (60, 150, 50), (30, 100, 30)],
    'sand.png':  [(220, 200, 140), (235, 215, 160), (200, 180, 120)],
    'brick.png': [(150, 60, 50), (170, 70, 55), (130, 50, 40)],
    'glass.png': [(200, 230, 255), (220, 240, 255), (180, 210, 240)],
}


def make_noise_texture(colors):
    img = Image.new('RGB', (SIZE, SIZE))
    for y in range(SIZE):
        for x in range(SIZE):
            img.putpixel((x, y), random.choice(colors))
    return img


def make_brick_texture():
    img = Image.new('RGB', (SIZE, SIZE), (150, 60, 50))
    mortar = (80, 40, 30)
    for x in range(SIZE):
        img.putpixel((x, 7), mortar)
        img.putpixel((x, 15), mortar)
    for y in range(0, 8):
        img.putpixel((7, y), mortar)
    for y in range(8, 16):
        img.putpixel((0, y), mortar)
    return img


def make_wood_texture():
    img = Image.new('RGB', (SIZE, SIZE))
    base = (110, 75, 40)
    dark = (70, 45, 20)
    for y in range(SIZE):
        for x in range(SIZE):
            if x in (0, 3, 8, 12, 15) or random.random() < 0.1:
                img.putpixel((x, y), dark)
            else:
                img.putpixel((x, y), base)
    return img


for name, colors in TEXTURES.items():
    if name == 'brick.png':
        img = make_brick_texture()
    elif name == 'wood.png':
        img = make_wood_texture()
    else:
        img = make_noise_texture(colors)

    path = os.path.join(OUT_DIR, name)
    img.save(path)
    print(f'saved: {path}')

print('done')