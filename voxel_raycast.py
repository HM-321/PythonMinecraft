import math
from dataclasses import dataclass

from ursina import Vec3


@dataclass(frozen=True)
class VoxelHit:
    block: object
    position: tuple[int, int, int]
    normal: Vec3
    distance: float


def _axis_values(origin, direction, cell):
    if direction > 0:
        return 1, (cell + 1 - origin) / direction, 1 / direction
    if direction < 0:
        return -1, (cell - origin) / direction, -1 / direction
    return 0, math.inf, math.inf


def cast(world, origin, direction, max_distance):
    """Colliderに依存せず、論理ブロック辞書を探索する3D DDA。"""
    length = direction.length()
    if length <= 1e-9 or max_distance <= 0:
        return None

    direction = direction / length

    # 論理ブロック(x, y, z)は、X/Zが中心基準、Yが[y-1, y]。
    # DDAの単位セルへ一致させるため座標系を平行移動する。
    ox = float(origin.x) + 0.5
    oy = float(origin.y) + 1.0
    oz = float(origin.z) + 0.5
    x = math.floor(ox)
    y = math.floor(oy)
    z = math.floor(oz)

    step_x, t_max_x, t_delta_x = _axis_values(ox, float(direction.x), x)
    step_y, t_max_y, t_delta_y = _axis_values(oy, float(direction.y), y)
    step_z, t_max_z, t_delta_z = _axis_values(oz, float(direction.z), z)

    distance = 0.0
    normal = Vec3(0, 0, 0)

    while distance <= max_distance:
        block = world.get_block(x, y, z)
        if block is not None:
            return VoxelHit(block, (x, y, z), normal, distance)

        if t_max_x <= t_max_y and t_max_x <= t_max_z:
            x += step_x
            distance = t_max_x
            t_max_x += t_delta_x
            normal = Vec3(-step_x, 0, 0)
        elif t_max_y <= t_max_z:
            y += step_y
            distance = t_max_y
            t_max_y += t_delta_y
            normal = Vec3(0, -step_y, 0)
        else:
            z += step_z
            distance = t_max_z
            t_max_z += t_delta_z
            normal = Vec3(0, 0, -step_z)

    return None
