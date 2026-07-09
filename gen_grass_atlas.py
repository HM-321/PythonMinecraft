from PIL import Image
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')

SIZE = 16

# 上面: 緑
top = Image.new('RGB', (SIZE, SIZE))
for y in range(SIZE):
    for x in range(SIZE):
        import random
        c = random.choice([(60, 160, 50), (70, 175, 55), (55, 150, 45)])
        top.putpixel((x, y), c)

# 横面: 上半分緑、下半分土
side = Image.new('RGB', (SIZE, SIZE))
for y in range(SIZE):
    for x in range(SIZE):
        import random
        if y < 4:
            c = random.choice([(60, 160, 50), (70, 175, 55), (55, 150, 45)])
        elif y < 6:
            c = random.choice([(80, 130, 50), (90, 100, 45), (110, 80, 40)])
        else:
            c = random.choice([(101, 67, 33), (120, 80, 40), (85, 55, 25)])
        side.putpixel((x, y), c)

# 下面: 土（既存のdirt.pngを流用してもOK）
bottom = Image.new('RGB', (SIZE, SIZE))
for y in range(SIZE):
    for x in range(SIZE):
        import random
        c = random.choice([(101, 67, 33), (120, 80, 40), (85, 55, 25)])
        bottom.putpixel((x, y), c)

# 縦に3枚結合 (16 x 48)
atlas = Image.new('RGB', (SIZE, SIZE * 3))
atlas.paste(top, (0, 0))          # 上部: top
atlas.paste(side, (0, SIZE))      # 中央: side
atlas.paste(bottom, (0, SIZE * 2))  # 下部: bottom

atlas.save(os.path.join(OUT_DIR, 'grass_atlas.png'))
side.save(os.path.join(OUT_DIR, 'grass_icon.png'))
print(f'saved: {os.path.join(OUT_DIR, "grass_atlas.png")}')