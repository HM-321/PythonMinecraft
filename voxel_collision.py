import math


EPSILON = 1e-6


def _world():
    import __main__
    return getattr(__main__, 'game', {}).get('world')


def _x_cells(center, radius):
    minimum = math.floor(center - radius + 0.5 + EPSILON)
    maximum = math.floor(center + radius + 0.5 - EPSILON)
    return range(minimum, maximum + 1)


def _y_cells(bottom, height):
    # 論理ブロックYは上面座標で、占有範囲は[y-1, y]。
    minimum = math.floor(bottom + EPSILON) + 1
    maximum = math.ceil(bottom + height - EPSILON)
    return range(minimum, maximum + 1)


def overlaps_player(world, x, y, z, radius, height):
    if world is None:
        return False
    for bx in _x_cells(x, radius):
        for bz in _x_cells(z, radius):
            for by in _y_cells(y, height):
                if world.has_block(bx, by, bz):
                    return True
    return False


def supporting_top(world, x, y, z, radius, max_drop=0.12):
    """足元直下にある床の上面Y。なければNone。"""
    if world is None:
        return None
    best = None
    minimum_top = y - max_drop
    maximum_top = y + 0.08
    for bx in _x_cells(x, radius):
        for bz in _x_cells(z, radius):
            start = math.floor(minimum_top) - 1
            end = math.ceil(maximum_top) + 1
            for by in range(start, end + 1):
                if minimum_top <= by <= maximum_top and world.has_block(bx, by, bz):
                    if best is None or by > best:
                        best = float(by)
    return best


def sweep_vertical(world, x, y, z, radius, height, delta):
    """Y移動を解決し、(新Y, 衝突したか)を返す。"""
    if world is None or delta == 0:
        return y + delta, False

    if delta < 0:
        next_y = y + delta
        floor_y = None
        for bx in _x_cells(x, radius):
            for bz in _x_cells(z, radius):
                minimum = math.floor(next_y) - 1
                maximum = math.ceil(y) + 1
                for by in range(minimum, maximum + 1):
                    if next_y - EPSILON <= by <= y + EPSILON:
                        if world.has_block(bx, by, bz):
                            if floor_y is None or by > floor_y:
                                floor_y = float(by)
        if floor_y is not None:
            return floor_y, True
        return next_y, False

    current_top = y + height
    next_top = current_top + delta
    ceiling_bottom = None
    for bx in _x_cells(x, radius):
        for bz in _x_cells(z, radius):
            minimum_y = math.floor(current_top) + 1
            maximum_y = math.ceil(next_top) + 1
            for by in range(minimum_y, maximum_y + 1):
                bottom = by - 1.0
                if current_top - EPSILON <= bottom <= next_top + EPSILON:
                    if world.has_block(bx, by, bz):
                        if ceiling_bottom is None or bottom < ceiling_bottom:
                            ceiling_bottom = bottom
    if ceiling_bottom is not None:
        return ceiling_bottom - height, True
    return y + delta, False
