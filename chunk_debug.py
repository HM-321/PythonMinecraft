from ursina import Entity, color, destroy, scene

from world import LOD_CHUNK_SIZE


class ChunkBoundaryDisplay:
    """現在いるチャンクだけを立体格子で表示する。"""

    MIN_Y = -32
    MAX_Y = 128
    HORIZONTAL_INTERVAL = 5

    def __init__(self):
        self.enabled = False
        self.entities = []
        self._last_chunk = None

    def toggle(self):
        self.enabled = not self.enabled

        if not self.enabled:
            self.clear()

        return self.enabled

    def clear(self):
        for entity in self.entities:
            destroy(entity)

        self.entities.clear()
        self._last_chunk = None

    def update(self, world, player):
        if not self.enabled or world is None or player is None:
            return

        chunk = world.chunk_key_at(player.x, player.z)

        if chunk == self._last_chunk:
            return

        self._rebuild(*chunk)

    def _add_line(self, position, scale, line_color):
        self.entities.append(
            Entity(
                parent=scene,
                model="cube",
                position=position,
                scale=scale,
                color=line_color,
                collider=None,
                unlit=True,
            )
        )

    def _rebuild(self, chunk_x, chunk_z):
        self.clear()
        self._last_chunk = (chunk_x, chunk_z)

        size = LOD_CHUNK_SIZE
        thickness = 0.035

        min_x = chunk_x * size - 0.5
        max_x = (chunk_x + 1) * size - 0.5
        min_z = chunk_z * size - 0.5
        max_z = (chunk_z + 1) * size - 0.5

        center_x = (min_x + max_x) / 2
        center_z = (min_z + max_z) / 2
        center_y = (self.MIN_Y + self.MAX_Y) / 2
        height = self.MAX_Y - self.MIN_Y

        vertical_color = color.rgba(255, 210, 40, 220)
        horizontal_color = color.rgba(255, 210, 40, 140)

        # 四隅の縦線
        for x in (min_x, max_x):
            for z in (min_z, max_z):
                self._add_line(
                    position=(x, center_y, z),
                    scale=(thickness, height, thickness),
                    line_color=vertical_color,
                )

        # 5ブロック間隔の水平枠
        for y in range(
            self.MIN_Y,
            self.MAX_Y + 1,
            self.HORIZONTAL_INTERVAL,
        ):
            self._add_line(
                position=(center_x, y, min_z),
                scale=(size, thickness, thickness),
                line_color=horizontal_color,
            )
            self._add_line(
                position=(center_x, y, max_z),
                scale=(size, thickness, thickness),
                line_color=horizontal_color,
            )
            self._add_line(
                position=(min_x, y, center_z),
                scale=(thickness, thickness, size),
                line_color=horizontal_color,
            )
            self._add_line(
                position=(max_x, y, center_z),
                scale=(thickness, thickness, size),
                line_color=horizontal_color,
            )
