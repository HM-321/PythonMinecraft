from ursina import Entity, Vec3, color, destroy, scene, time
from block_types import BLOCK_TYPES

SAND_ID = next(i for i, block in enumerate(BLOCK_TYPES) if block[0] == 'Sand')
FALL_ACCELERATION = 24.0
TERMINAL_SPEED = 28.0
COLUMN_INTERVAL = 0.11
MIN_Y = -64


class SandPhysics:
    def __init__(self, world, authoritative=True):
        self.world = world
        self.authoritative = authoritative
        self.falling = []
        self.scan_timer = 0.15
        self.column_cooldowns = {}

    def clear(self):
        for item in self.falling:
            destroy(item['entity'])
        self.falling.clear()
        self.column_cooldowns.clear()

    def update(self):
        dt = min(time.dt, 0.05)
        self._update_visuals(dt)
        if not self.authoritative:
            return

        for column in tuple(self.column_cooldowns):
            remaining = self.column_cooldowns[column] - dt
            if remaining <= 0:
                self.column_cooldowns.pop(column, None)
            else:
                self.column_cooldowns[column] = remaining

        self.scan_timer -= dt
        if self.scan_timer <= 0:
            self.scan_timer = 0.06
            self._start_unstable_sand()

    def _make_visual(self, x, y, z):
        _, block_color, texture_info = BLOCK_TYPES[SAND_ID]
        texture = texture_info.get('atlas') if isinstance(texture_info, dict) else texture_info
        entity = Entity(
            parent=scene,
            model='cube',
            texture=texture,
            color=block_color,
            position=(x, y - 0.5, z),
            collider=None,
            origin_y=0,
        )
        if entity.texture:
            entity.texture.filtering = None
        return entity

    def start_remote(self, x, y, z, fall_id=None):
        position = (int(x), int(y), int(z))
        existing = self.world.get_block(*position)
        if existing:
            self.world.remove_block(existing)
        self.falling.append({
            'id': fall_id,
            'entity': self._make_visual(*position),
            'x': position[0],
            'z': position[2],
            'y': float(position[1]),
            'velocity': 0.0,
            'remote': True,
        })

    def land_remote(self, fall_id, x, y, z, block_id=SAND_ID):
        for index, item in enumerate(self.falling):
            if item.get('id') == fall_id:
                destroy(item['entity'])
                self.falling.pop(index)
                break
        if not self.world.get_block(x, y, z):
            self.world.place_block(x, y, z, block_id)

    def _start_unstable_sand(self):
        candidates = []
        for block in tuple(self.world.boxes):
            if getattr(block, 'block_type', None) != SAND_ID:
                continue
            x, y, z = block.block_position
            if y <= MIN_Y or self.world.get_block(x, y - 1, z) is not None:
                continue
            column = (x, z)
            if column in self.column_cooldowns:
                continue
            candidates.append((y, x, z, block))

        if not candidates:
            return

        # 各列の最下段を優先し、1スキャンにつき1個だけ開始する。
        y, x, z, block = min(candidates)
        self.world.remove_block(block)
        self.falling.append({
            'id': None,
            'entity': self._make_visual(x, y, z),
            'x': x,
            'z': z,
            'y': float(y),
            'velocity': 0.0,
            'remote': False,
        })
        self.column_cooldowns[(x, z)] = COLUMN_INTERVAL

    def _update_visuals(self, dt):
        alive = []
        for item in self.falling:
            if item.get('remote'):
                # Remoteはサーバーの着地通知まで視覚的に落とし続ける。
                item['velocity'] = min(TERMINAL_SPEED, item['velocity'] + FALL_ACCELERATION * dt)
                item['y'] -= item['velocity'] * dt
                item['entity'].y = item['y'] - 0.5
                alive.append(item)
                continue

            item['velocity'] = min(TERMINAL_SPEED, item['velocity'] + FALL_ACCELERATION * dt)
            next_y = item['y'] - item['velocity'] * dt
            landing_y = self._landing_y(item['x'], item['z'], item['y'], next_y)
            if landing_y is None:
                item['y'] = next_y
                item['entity'].y = item['y'] - 0.5
                alive.append(item)
                continue

            destroy(item['entity'])
            if not self.world.get_block(item['x'], landing_y, item['z']):
                self.world.place_block(item['x'], landing_y, item['z'], SAND_ID)
            self.column_cooldowns[(item['x'], item['z'])] = COLUMN_INTERVAL
        self.falling = alive

    def _landing_y(self, x, z, current_y, next_y):
        start = int(current_y - 1e-6)
        end = max(MIN_Y, int(next_y) - 1)
        for support_y in range(start, end - 1, -1):
            if self.world.get_block(x, support_y, z) is not None:
                return support_y + 1
        if next_y <= MIN_Y:
            return MIN_Y
        return None
