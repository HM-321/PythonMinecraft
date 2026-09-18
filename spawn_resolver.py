"""全ゲームモード共通の安全スポーン探索。"""

import math

from config import PLAYER_HEIGHT, PLAYER_RADIUS, WORLD_SIZE


SPAWN_EPSILON = 0.02


def _positions(world):
    """ワールド内の全ブロック座標を取得する。"""
    block_data = getattr(world, "block_data_by_position", None)

    if block_data is not None:
        return tuple(block_data.keys())

    return tuple(world.blocks.keys())


def _has_block(world, x, y, z):
    """指定座標にブロックが存在するか確認する。"""
    if hasattr(world, "has_block"):
        return bool(world.has_block(x, y, z))

    return (int(x), int(y), int(z)) in world.blocks


def _body_columns(x, z):
    """プレイヤーAABBが水平方向に触れるブロック列を返す。"""
    margin = 1e-6

    min_x = math.floor(
        x - PLAYER_RADIUS + 0.5 + margin
    )
    max_x = math.floor(
        x + PLAYER_RADIUS + 0.5 - margin
    )
    min_z = math.floor(
        z - PLAYER_RADIUS + 0.5 + margin
    )
    max_z = math.floor(
        z + PLAYER_RADIUS + 0.5 - margin
    )

    for block_x in range(min_x, max_x + 1):
        for block_z in range(min_z, max_z + 1):
            yield block_x, block_z


def is_safe_spawn(world, x, floor_y, z):
    """床と身体空間が確保されているか確認する。"""
    columns = tuple(_body_columns(x, z))

    if not columns:
        return False

    # プレイヤーAABBの下全体に床が必要。
    if any(
        not _has_block(
            world,
            block_x,
            floor_y,
            block_z,
        )
        for block_x, block_z in columns
    ):
        return False

    # 足元から頭上まで空いている必要がある。
    top_y = math.ceil(
        floor_y + PLAYER_HEIGHT
    )

    for block_x, block_z in columns:
        for block_y in range(
            floor_y + 1,
            top_y + 1,
        ):
            if _has_block(
                world,
                block_x,
                block_y,
                block_z,
            ):
                return False

    return True


def find_safe_spawn(
    world,
    preferred_x=0.0,
    preferred_z=0.0,
):
    """希望地点から外側へ安全な地表を探索する。"""
    positions = _positions(world)
    columns = {}

    for x, y, z in positions:
        key = (int(x), int(z))
        columns.setdefault(key, []).append(int(y))

    origin_x = int(round(preferred_x))
    origin_z = int(round(preferred_z))
    max_radius = max(WORLD_SIZE, 32)

    for radius in range(max_radius + 1):
        for dx in range(
            -radius,
            radius + 1,
        ):
            for dz in range(
                -radius,
                radius + 1,
            ):
                if max(
                    abs(dx),
                    abs(dz),
                ) != radius:
                    continue

                x = origin_x + dx
                z = origin_z + dz

                floor_candidates = columns.get(
                    (x, z),
                    (),
                )

                for floor_y in sorted(
                    floor_candidates,
                    reverse=True,
                ):
                    if is_safe_spawn(
                        world,
                        float(x),
                        floor_y,
                        float(z),
                    ):
                        return (
                            float(x) + SPAWN_EPSILON,
                            float(floor_y) + SPAWN_EPSILON,
                            float(z) + SPAWN_EPSILON,
                        )

    # 見つからない場合は最高地点より上へ退避。
    highest_y = max(
        (
            y
            for _x, y, _z in positions
        ),
        default=2,
    )

    return (
        0.0,
        float(highest_y + 3),
        0.0,
    )


def validate_or_resolve_spawn(
    world,
    position,
):
    """保存座標が危険な場合だけ安全地点へ変更する。"""
    try:
        x, y, z = map(float, position)
    except (TypeError, ValueError):
        return find_safe_spawn(world)

    floor_y = round(y)

    if (
        abs(y - floor_y) <= 0.15
        and is_safe_spawn(
            world,
            x,
            int(floor_y),
            z,
        )
    ):
        return x, y, z

    return find_safe_spawn(world)
