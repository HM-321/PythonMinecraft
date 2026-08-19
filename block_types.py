from ursina import color

# textures フィールド:
#   str → 全面同じ
#   dict {'atlas': ..., 'icon': ...} → 面別 + アイコン別指定
BLOCK_TYPES = [
    ('Grass', color.white, {'atlas': 'textures/grass_atlas.png',
                             'icon': 'textures/grass_icon.png'}),
    ('Dirt',  color.white, 'textures/dirt.png'),
    ('Stone', color.white, 'textures/stone.png'),
    ('Wood',  color.white, 'textures/wood.png'),
    ('Ice',   color.white, 'textures/ice.png'),
    ('Sand',  color.white, 'textures/sand.png'),
    ('Brick', color.white, 'textures/brick.png'),
    ('Glass', color.rgba(180, 220, 240, 50), None),
    ('Log',   color.white, {'atlas': 'textures/log_atlas.png',
                             'icon': 'textures/log_icon.png',
                             'rotatable': True}),
]

HOTBAR_ORDER = [0, 1, 2, 8, 3, 4, 5, 6, 7]