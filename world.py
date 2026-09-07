import json
import os
from collections import defaultdict
from datetime import datetime

from panda3d.core import TransparencyAttrib, Texture
from ursina import Entity, Mesh, Vec3, color, destroy, scene

from block_types import BLOCK_TYPES
from config import SAVE_VERSION, WORLD_SIZE
from custom_mesh import make_face_atlas_cube
from terrain_generator import TerrainGenerator


LOD_CHUNK_SIZE = 10


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        self.boxes = []
        self.blocks_by_position = {}
        # チャンクごとのブロック座標索引
        self.blocks_by_chunk = defaultdict(set)

        # 遠距離表示用。チャンクごと、ブロック種類ごとに上面を結合する。
        self.lod_entities = {}
        self.dirty_lod_chunks = set()
        self.lod_enabled = False
        self.visible_near_chunks = set()
        self.visible_lod_chunks = set()
        self.world_type = 'flat'
        self.seed = 0
        self.terrain_heights = {}

    @staticmethod
    def _position_key(x, y, z):
        return int(round(x)), int(round(y)), int(round(z))

    @staticmethod
    def _chunk_key(x, z):
        return int(x) // LOD_CHUNK_SIZE, int(z) // LOD_CHUNK_SIZE

    def get_block(self, x, y, z):
        return self.blocks_by_position.get(self._position_key(x, y, z))

    def place_block(self, x, y, z, block_id, orientation='y'):
        position = self._position_key(x, y, z)
        existing = self.blocks_by_position.get(position)
        if existing is not None:
            return existing

        name, block_color, texture_info = BLOCK_TYPES[block_id]
        orientation = orientation if orientation in ('x', 'y', 'z') else 'y'

        if isinstance(texture_info, dict) and 'atlas' in texture_info:
            block = Entity(
                color=block_color,
                model=make_face_atlas_cube(orientation),
                position=(position[0], position[1] - 0.5, position[2]),
                texture=texture_info['atlas'],
                parent=scene,
                collider='box',
            )
            block.custom_mesh = True
            block.orientation = orientation
        else:
            block = Entity(
                color=block_color,
                model='cube',
                position=position,
                texture=texture_info,
                parent=scene,
                origin_y=0.5,
                collider='box',
            )
            block.custom_mesh = False
            block.orientation = 'y'

        if block.texture:
            block.texture.filtering = None

        block.block_type = block_id
        block.block_position = position

        if name == 'Glass':
            block.setTransparency(TransparencyAttrib.M_alpha)
            block.set_bin('transparent', 30)
            block.setDepthWrite(False)

        chunk_key = self._chunk_key(position[0], position[2])
        self.boxes.append(block)
        self.blocks_by_position[position] = block
        self.blocks_by_chunk[chunk_key].add(position)
        self.dirty_lod_chunks.add(chunk_key)
        return block

    def remove_block(self, block):
        position = getattr(block, 'block_position', None)
        if position is None:
            position = self._position_key(block.x, block.y, block.z)
        else:
            position = self._position_key(*position)

        registered = self.blocks_by_position.pop(position, None)
        target = registered or block

        try:
            self.boxes.remove(target)
        except ValueError:
            return False

        # Normal地形は地下を最初からEntity化せず、掘った時だけ生成する。
        replacement = None
        if self.world_type == 'normal' and position[1] > -8:
            below = (position[0], position[1] - 1, position[2])
            if below not in self.blocks_by_position:
                surface_y = self.terrain_heights.get(
                    (position[0], position[2]), position[1]
                )
                replacement_id = 1 if below[1] >= surface_y - 3 else 2
                replacement = (below, replacement_id)

        destroy(target)
        chunk_key = self._chunk_key(position[0], position[2])
        chunk_positions = self.blocks_by_chunk.get(chunk_key)
        if chunk_positions is not None:
            chunk_positions.discard(position)
            if not chunk_positions:
                self.blocks_by_chunk.pop(chunk_key, None)
        self.dirty_lod_chunks.add(chunk_key)
        if replacement is not None:
            below, replacement_id = replacement
            self.place_block(*below, replacement_id)
        return True

    def clear(self):
        for block in self.boxes:
            destroy(block)
        self.boxes.clear()
        self.blocks_by_position.clear()
        self.blocks_by_chunk.clear()
        self.clear_lod()

    def clear_lod(self):
        for entities in self.lod_entities.values():
            for entity in entities:
                destroy(entity)
        self.lod_entities.clear()
        self.dirty_lod_chunks.clear()
        self.lod_enabled = False
        self.visible_near_chunks.clear()
        self.visible_lod_chunks.clear()

    def dispose(self):
        self.clear()

    def generate_normal(self, seed=0):
        self.world_type = 'normal'
        self.seed = int(seed)
        generator = TerrainGenerator(self.seed)
        self.terrain_heights = generator.generate_surface(self, WORLD_SIZE)
        center = WORLD_SIZE // 2
        return self.terrain_heights.get((center, center), 6) + 1

    def generate_flat(self):
        self.world_type = 'flat'
        for z in range(WORLD_SIZE):
            for x in range(WORLD_SIZE):
                self.place_block(x, 0, z, 0)

    @staticmethod
    def _is_transparent(block):
        if block is None:
            return True
        name, _, texture_info = BLOCK_TYPES[block.block_type]
        return name == 'Glass' or texture_info is None

    @staticmethod
    def _face_material(block, face_name):
        _, block_color, texture_info = BLOCK_TYPES[block.block_type]
        if not isinstance(texture_info, dict):
            return texture_info, (0.0, 1.0), block_color

        texture_path = texture_info.get('atlas')
        orientation = getattr(block, 'orientation', 'y')
        top_face = f'+{orientation}'
        bottom_face = f'-{orientation}'

        if face_name == top_face:
            uv_range = (2 / 3, 1.0)
        elif face_name == bottom_face:
            uv_range = (0.0, 1 / 3)
        else:
            uv_range = (1 / 3, 2 / 3)
        return texture_path, uv_range, block_color

    def rebuild_dirty_lod(self):
        if not self.dirty_lod_chunks:
            return

        dirty = tuple(self.dirty_lod_chunks)
        self.dirty_lod_chunks.clear()
        for chunk_key in dirty:
            self._rebuild_lod_chunk(chunk_key)

    def _rebuild_lod_chunk(self, chunk_key):
        old_entities = self.lod_entities.pop(chunk_key, [])
        for entity in old_entities:
            destroy(entity)

        chunk_x, chunk_z = chunk_key
        start_x = chunk_x * LOD_CHUNK_SIZE
        start_z = chunk_z * LOD_CHUNK_SIZE
        end_x = start_x + LOD_CHUNK_SIZE
        end_z = start_z + LOD_CHUNK_SIZE

        # 面名: (隣接座標, 4頂点)。論理Yはブロック上面を表す。
        face_definitions = {
            '+y': ((0, 1, 0), lambda x, y, z: [
                Vec3(x - .5, y, z - .5), Vec3(x - .5, y, z + .5),
                Vec3(x + .5, y, z + .5), Vec3(x + .5, y, z - .5),
            ]),
            '-y': ((0, -1, 0), lambda x, y, z: [
                Vec3(x - .5, y - 1, z + .5), Vec3(x - .5, y - 1, z - .5),
                Vec3(x + .5, y - 1, z - .5), Vec3(x + .5, y - 1, z + .5),
            ]),
            '+x': ((1, 0, 0), lambda x, y, z: [
                Vec3(x + .5, y - 1, z - .5), Vec3(x + .5, y, z - .5),
                Vec3(x + .5, y, z + .5), Vec3(x + .5, y - 1, z + .5),
            ]),
            '-x': ((-1, 0, 0), lambda x, y, z: [
                Vec3(x - .5, y - 1, z + .5), Vec3(x - .5, y, z + .5),
                Vec3(x - .5, y, z - .5), Vec3(x - .5, y - 1, z - .5),
            ]),
            '+z': ((0, 0, 1), lambda x, y, z: [
                Vec3(x + .5, y - 1, z + .5), Vec3(x + .5, y, z + .5),
                Vec3(x - .5, y, z + .5), Vec3(x - .5, y - 1, z + .5),
            ]),
            '-z': ((0, 0, -1), lambda x, y, z: [
                Vec3(x - .5, y - 1, z - .5), Vec3(x - .5, y, z - .5),
                Vec3(x + .5, y, z - .5), Vec3(x + .5, y - 1, z - .5),
            ]),
        }

        # texture, UV範囲, 色ごとに結合する。透明ブロックは近距離表示のみ。
        groups = defaultdict(lambda: {'vertices': [], 'triangles': [], 'uvs': []})
        for position in self.blocks_by_chunk.get(chunk_key, ()):
            x, y, z = position
            block = self.blocks_by_position.get(position)
            if block is None or self._is_transparent(block):
                continue

            for face_name, (offset, make_vertices) in face_definitions.items():
                ox, oy, oz = offset
                neighbor = self.get_block(x + ox, y + oy, z + oz)
                if neighbor is not None and not self._is_transparent(neighbor):
                    continue

                texture_path, (uv_min, uv_max), block_color = self._face_material(
                    block, face_name
                )
                color_key = tuple(float(value) for value in block_color)
                group = groups[(texture_path, uv_min, uv_max, color_key)]
                base = len(group['vertices'])
                group['vertices'].extend(make_vertices(x, y, z))
                group['triangles'].extend([
                    base, base + 1, base + 2,
                    base, base + 2, base + 3,
                ])
                group['uvs'].extend([
                    (0, uv_min), (0, uv_max),
                    (1, uv_max), (1, uv_min),
                ])

        new_entities = []
        for (texture_path, _uv_min, _uv_max, color_key), data in groups.items():
            lod = Entity(
                parent=scene,
                model=Mesh(
                    vertices=data['vertices'],
                    triangles=data['triangles'],
                    uvs=data['uvs'],
                    mode='triangle',
                    static=True,
                ),
                texture=texture_path,
                color=color.rgba(*color_key),
                collider=None,
                double_sided=True,
                enabled=self.lod_enabled,
            )
            if lod.texture:
                lod.texture.filtering = None
                lod.texture.wrap_u = Texture.WM_repeat
                lod.texture.wrap_v = Texture.WM_repeat
            new_entities.append(lod)

        self.lod_entities[chunk_key] = new_entities

    def _set_near_chunk_enabled(self, chunk_key, enabled, player_y,
                                vertical_distance):
        for position in self.blocks_by_chunk.get(chunk_key, ()):
            block = self.blocks_by_position.get(position)
            if block is not None:
                block.enabled = (
                    enabled
                    and abs(position[1] - player_y) < vertical_distance
                )

    def _set_lod_chunk_enabled(self, chunk_key, enabled):
        for entity in self.lod_entities.get(chunk_key, ()):
            entity.enabled = enabled

    def update_visibility(self, player_x, player_y, player_z,
                          vertical_distance, render_distance):
        self.rebuild_dirty_lod()

        chunk_radius = LOD_CHUNK_SIZE * 0.75
        near_distance = max(8.0, render_distance * 0.6)
        lod_distance = render_distance + chunk_radius
        near_distance2 = near_distance * near_distance
        lod_distance2 = lod_distance * lod_distance
        high_altitude = abs(player_y) >= vertical_distance - 2

        next_near = set()
        next_lod = set()
        all_chunks = set(self.lod_entities)
        all_chunks.update(self.blocks_by_chunk)

        for chunk_key in all_chunks:
            chunk_x, chunk_z = chunk_key
            center_x = chunk_x * LOD_CHUNK_SIZE + LOD_CHUNK_SIZE / 2
            center_z = chunk_z * LOD_CHUNK_SIZE + LOD_CHUNK_SIZE / 2
            distance2 = (
                (center_x - player_x) ** 2
                + (center_z - player_z) ** 2
            )
            if not high_altitude and distance2 <= near_distance2:
                next_near.add(chunk_key)
            elif distance2 <= lod_distance2:
                next_lod.add(chunk_key)

        # 全ブロックを毎回触らず、表示状態が変わったチャンクだけ更新する。
        for chunk_key in self.visible_near_chunks - next_near:
            self._set_near_chunk_enabled(
                chunk_key, False, player_y, vertical_distance
            )
        for chunk_key in next_near - self.visible_near_chunks:
            self._set_near_chunk_enabled(
                chunk_key, True, player_y, vertical_distance
            )

        for chunk_key in self.visible_lod_chunks - next_lod:
            self._set_lod_chunk_enabled(chunk_key, False)
        for chunk_key in next_lod - self.visible_lod_chunks:
            self._set_lod_chunk_enabled(chunk_key, True)

        self.visible_near_chunks = next_near
        self.visible_lod_chunks = next_lod
        self.lod_enabled = bool(next_lod)

    def get_chunk_positions(self, chunk_x, chunk_z):
        return tuple(self.blocks_by_chunk.get((chunk_x, chunk_z), ()))

    def get_chunk_blocks(self, chunk_x, chunk_z):
        return tuple(
            self.blocks_by_position[position]
            for position in self.get_chunk_positions(chunk_x, chunk_z)
            if position in self.blocks_by_position
        )

    def loaded_chunk_keys(self):
        return tuple(self.blocks_by_chunk.keys())

    def save(self, player_entity):
        data = {
            'version': SAVE_VERSION,
            'name': os.path.basename(self.save_path)[:-5],
            'last_played': datetime.now().isoformat(),
            'player': [player_entity.x, player_entity.y, player_entity.z],
            'world_type': self.world_type,
            'seed': self.seed,
            'terrain_heights': [[x, z, y] for (x, z), y in self.terrain_heights.items()],
            'blocks': [self._block_to_save(block) for block in self.boxes],
        }
        with open(self.save_path, 'w', encoding='utf-8') as save_file:
            json.dump(data, save_file, ensure_ascii=False)
        print(f'saved: {self.save_path}')

    @staticmethod
    def _block_to_save(block):
        x, y, z = getattr(
            block,
            'block_position',
            (block.x, block.y, block.z),
        )
        return [
            int(x),
            int(y),
            int(z),
            block.block_type,
            getattr(block, 'orientation', 'y'),
        ]

    def load(self, player_entity):
        with open(self.save_path, encoding='utf-8') as save_file:
            data = json.load(save_file)

        self.clear()
        self.world_type = data.get('world_type', 'flat')
        self.seed = int(data.get('seed', 0))
        self.terrain_heights = {
            (int(x), int(z)): int(y)
            for x, z, y in data.get('terrain_heights', [])
        }
        for entry in data['blocks']:
            bx, by, bz, block_id = entry[:4]
            orientation = entry[4] if len(entry) > 4 else 'y'
            self.place_block(bx, by, bz, block_id, orientation=orientation)

        player_entity.position = tuple(data['player'])
        print(f'loaded: {self.save_path}, boxes count={len(self.boxes)}')
