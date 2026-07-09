from PIL import Image
import random
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')
SIZE = 16


# 上下面: 年輪
def make_ring_texture():
    img = Image.new('RGB', (SIZE, SIZE))
    center = (SIZE / 2 - 0.5, SIZE / 2 - 0.5)
    for y in range(SIZE):
        for x in range(SIZE):
            dx = x - center[0]
            dy = y - center[1]
            dist = (dx * dx + dy * dy) ** 0.5
            # 年輪リング
            ring = int(dist) % 3
            if ring == 0:
                c = (60, 40, 20)
            elif ring == 1:
                c = (140, 100, 60)
            else:
                c = (120, 85, 50)
            # ノイズ
            noise = random.randint(-10, 10)
            c = tuple(max(0, min(255, ch + noise)) for ch in c)
            img.putpixel((x, y), c)
    return img


# 側面: 樹皮
def make_bark_texture():
    img = Image.new('RGB', (SIZE, SIZE))
    for y in range(SIZE):
        for x in range(SIZE):
            # 縦の縞模様
            base = 80 if (x + random.randint(-1, 1)) % 4 < 2 else 55
            c = (base + random.randint(-15, 15),
                 int(base * 0.7) + random.randint(-10, 10),
                 int(base * 0.4) + random.randint(-5, 5))
            c = tuple(max(0, min(255, ch)) for ch in c)
            img.putpixel((x, y), c)
    return img


top = make_ring_texture()
side = make_bark_texture()
bottom = make_ring_texture()

atlas = Image.new('RGB', (SIZE, SIZE * 3))
atlas.paste(top, (0, 0))
atlas.paste(side, (0, SIZE))
atlas.paste(bottom, (0, SIZE * 2))

path = os.path.join(OUT_DIR, 'log_atlas.png')
atlas.save(path)
side.save(os.path.join(OUT_DIR, 'log_icon.png'))
print(f'saved: {path}')