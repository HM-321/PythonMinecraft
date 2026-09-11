import math


GRASS_ID = 0
DIRT_ID = 1
STONE_ID = 2
GENERATOR_ID = 'grassland_v1'
TREE_GENERATOR_ID = 'grassland_v2'
LOG_ID = 8
LEAVES_ID = 6
BASE_HEIGHT = 4
MIN_SURFACE = 1
MAX_SURFACE = 10
BOTTOM_Y = -4


def _hash01(seed, x, z):
    value = (int(seed) ^ (x * 0x9E3779B185EBCA87) ^ (z * 0xC2B2AE3D27D4EB4F))
    value &= (1 << 64) - 1
    value ^= value >> 30
    value = (value * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    value ^= value >> 27
    value = (value * 0x94D049BB133111EB) & ((1 << 64) - 1)
    value ^= value >> 31
    return value / float((1 << 64) - 1)


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _value_noise(seed, x, z, scale):
    gx = math.floor(x / scale)
    gz = math.floor(z / scale)
    tx = _smooth((x / scale) - gx)
    tz = _smooth((z / scale) - gz)
    a = _hash01(seed, gx, gz)
    b = _hash01(seed, gx + 1, gz)
    c = _hash01(seed, gx, gz + 1)
    d = _hash01(seed, gx + 1, gz + 1)
    top = a + (b - a) * tx
    bottom = c + (d - c) * tx
    return top + (bottom - top) * tz


def surface_height(seed, x, z, world_size):
    broad = (_value_noise(seed, x, z, 24.0) - 0.5) * 8.0
    detail = (_value_noise(seed ^ 0xA5A5A5A5A5A5A5A5, x, z, 10.0) - 0.5) * 3.0
    height = BASE_HEIGHT + broad + detail

    # 中央付近を緩やかにして初期スポーンを安定させる。
    center = (world_size - 1) / 2.0
    distance = math.hypot(x - center, z - center)
    if distance < 7.0:
        blend = _smooth(distance / 7.0)
        height = BASE_HEIGHT + (height - BASE_HEIGHT) * blend

    return max(MIN_SURFACE, min(MAX_SURFACE, int(round(height))))


def iter_grassland_blocks(seed, world_size):
    for z in range(world_size):
        for x in range(world_size):
            top = surface_height(seed, x, z, world_size)
            for y in range(BOTTOM_Y, top + 1):
                if y == top:
                    block_id = GRASS_ID
                elif y >= top - 3:
                    block_id = DIRT_ID
                else:
                    block_id = STONE_ID
                yield x, y, z, block_id, 'y'



def _tree_candidates(seed, world_size):
    """決定論的な候補から、近すぎる木を除外して返す。"""
    center = (world_size - 1) / 2.0
    candidates = []
    for z in range(3, world_size - 3):
        for x in range(3, world_size - 3):
            if math.hypot(x - center, z - center) < 8.0:
                continue
            chance = _hash01(seed ^ 0xD1B54A32D192ED03, x, z)
            if chance >= 0.012:
                continue
            top = surface_height(seed, x, z, world_size)
            neighbors = [
                surface_height(seed, x + dx, z + dz, world_size)
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ]
            if max(abs(top - value) for value in neighbors) > 1:
                continue
            candidates.append((chance, x, z, top))

    # Stable priority makes spacing independent of iteration direction.
    candidates.sort()
    accepted = []
    for chance, x, z, top in candidates:
        if any((x - tx) ** 2 + (z - tz) ** 2 < 64 for _, tx, tz, _ in accepted):
            continue
        accepted.append((chance, x, z, top))
    return accepted


def iter_tree_blocks(seed, world_size):
    for chance, x, z, top in _tree_candidates(seed, world_size):
        trunk_height = 4 + int(
            _hash01(seed ^ 0x94D049BB133111EB, x, z) * 3
        )
        trunk_top = top + trunk_height

        for y in range(top + 1, trunk_top + 1):
            yield x, y, z, LOG_ID, 'y'

        # Compact rounded canopy: two broad layers, one shoulder, one crown.
        for dy, radius in ((-2, 2), (-1, 2), (0, 2), (1, 1)):
            y = trunk_top + dy
            for dz in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if radius == 2 and abs(dx) == 2 and abs(dz) == 2:
                        continue
                    if dx == 0 and dz == 0 and y <= trunk_top:
                        continue
                    yield x + dx, y, z + dz, LEAVES_ID, 'y'


def iter_grassland_v2_blocks(seed, world_size):
    yield from iter_grassland_blocks(seed, world_size)
    yield from iter_tree_blocks(seed, world_size)
