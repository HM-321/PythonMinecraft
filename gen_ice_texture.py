import os
import random

from PIL import Image


SIZE = 16
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')
OUTPUT_PATH = os.path.join(OUT_DIR, 'ice.png')

ICE_COLORS = [
    (61, 143, 202),
    (72, 157, 214),
    (85, 169, 222),
    (53, 130, 190),
]
CRACK_COLORS = [
    (37, 105, 172),
    (48, 120, 184),
]
HIGHLIGHT_COLORS = [
    (138, 202, 238),
    (157, 215, 246),
]

random.seed(79)
texture = Image.new('RGB', (SIZE, SIZE))

for y in range(SIZE):
    for x in range(SIZE):
        texture.putpixel((x, y), random.choice(ICE_COLORS))

# 淡いハイライトと細いひびで、Minecraftの氷らしい冷たい表情を作る。
for _ in range(12):
    x = random.randrange(SIZE)
    y = random.randrange(SIZE)
    texture.putpixel((x, y), random.choice(HIGHLIGHT_COLORS))
    if x + 1 < SIZE:
        texture.putpixel((x + 1, y), random.choice(HIGHLIGHT_COLORS))

for start_x, start_y, length in ((2, 1, 7), (11, 4, 5), (5, 9, 6), (13, 12, 3)):
    for offset in range(length):
        x = start_x + offset
        y = start_y + offset // 2
        if x < SIZE and y < SIZE:
            texture.putpixel((x, y), random.choice(CRACK_COLORS))

os.makedirs(OUT_DIR, exist_ok=True)
texture.save(OUTPUT_PATH)
print(f'saved: {OUTPUT_PATH}')