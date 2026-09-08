import json
import os
from collections import defaultdict
from datetime import datetime

from panda3d.core import TransparencyAttrib, Texture
from ursina import Entity, Mesh, Vec3, color, destroy, scene

from block_types import BLOCK_TYPES
from config import SAVE_VERSION, WORLD_SIZE
from custom_mesh import make_face_atlas_cube


LOD_CHUNK_SIZE = 10
SAND_BLOCK_ID = 5


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        self.boxes = []
        self.blocks_by_position = {}
        self.sand_positions = set()
        # チャンクごとのブロック座標索引
        self.blocks_by_chunk = defaultdict(set)

        # 遠距離表示用。チャンクごと、ブロック種類ごとに上面を結合する。
        self.lod_entities = {}
        self.dirty_lod_chunks = set()
        self.lod_enabled = False
        self._high_altitude_lod = False
        self.visible_lod_chunks = set()

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
        if block_id == SAND_BLOCK_ID:
            self.sand_positions.add(position)
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
        self.sand_positions.discard(position)
        target = registered or block

        try:
            self.boxes.remove(target)
        except ValueError:
            return False

        destroy(target)
        chunk_key = self._chunk_key(position[0], position[2])
        chunk_positions = self.blocks_by_chunk.get(chunk_key)
        if chunk_positions is not None:
            chunk_positions.discard(position)
            if not chunk_positions:
                self.blocks_by_chunk.pop(chunk_key, None)
        self.dirty_lod_chunks.add(chunk_key)
        return True

    def clear(self):
        for block in self.boxes:
            destroy(block)
        self.boxes.clear()
        self.blocks_by_position.clear()
        self.sand_positions.clear()
        self.blocks_by_chunk.clear()
        self.clear_lod()

    def clear_lod(self):
        for entities in self.lod_entities.values():
            for entity in entities:
                destroy(entity)
        self.lod_entities.clear()
        self.dirty_lod_chunks.clear()
        self.lod_enabled = False
        self._high_altitude_lod = False
        self.visible_lod_chunks.clear()

    def dispose(self):
        self.clear()

    def generate_flat(self):
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

    def rebuild_dirty_lod(self, max_chunks=1):
        # LOD再生成を複数フレームへ分散して、一括停止を避ける。
        for _ in range(max_chunks):
            if not self.dirty_lod_chunks:
                return
            self._rebuild_lod_chunk(self.dirty_lod_chunks.pop())

    def _rebuild_lod_chunk(self, chunk_key):
        old_entities = self.lod_entities.pop(chunk_key, [])
        for entity in old_entities:
            entity.enabled = False
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
                enabled=(
                    hasattr(self, "visible_lod_chunks")
                    and chunk_key in self.visible_lod_chunks
                ),
            )
            if lod.texture:
                lod.texture.filtering = None
                lod.texture.wrap_u = Texture.WM_repeat
                lod.texture.wrap_v = Texture.WM_repeat
            new_entities.append(lod)

        self.lod_entities[chunk_key] = new_entities

    def update_visibility(self, player_x, player_y, player_z,
                          vertical_distance, render_distance):
        self.rebuild_dirty_lod()
        chunk_radius = LOD_CHUNK_SIZE * 0.75
        near_distance = max(8.0, render_distance * 0.6)
        lod_distance = render_distance + chunk_radius
        near_distance2 = near_distance * near_distance
        lod_distance2 = lod_distance * lod_distance
        # 境界付近で通常描画とLODが往復しないようヒステリシスを持たせる。
        # Render Distance 20の場合、上昇時はY=22、下降時はY=16で切り替わる。
        height = abs(player_y)
        enable_height = vertical_distance + 2
        disable_height = max(6, vertical_distance - 4)
        if self._high_altitude_lod:
            if height <= disable_height:
                self._high_altitude_lod = False
        elif height >= enable_height:
            self._high_altitude_lod = True
        high_altitude = self._high_altitude_lod

        # 足元を中心とした半径2ブロックが触れるチャンクだけ保護する。
        # 通常は1チャンク、境界付近でも最大4チャンクに制限される。
        protection_radius = 2
        min_chunk_x, min_chunk_z = self._chunk_key(
            player_x - protection_radius,
            player_z - protection_radius,
        )
        max_chunk_x, max_chunk_z = self._chunk_key(
            player_x + protection_radius,
            player_z + protection_radius,
        )
        protected_chunks = {
            (chunk_x, chunk_z)
            for chunk_x in range(min_chunk_x, max_chunk_x + 1)
            for chunk_z in range(min_chunk_z, max_chunk_z + 1)
        }

        near_chunks = set()
        lod_chunks = set()
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

            if chunk_key in protected_chunks:
                # 足元と建築中のチャンクは通常Entityだけを使う。
                near_chunks.add(chunk_key)
            elif distance2 <= near_distance2:
                near_chunks.add(chunk_key)
                if high_altitude and chunk_key in self.lod_entities:
                    lod_chunks.add(chunk_key)
            elif distance2 <= lod_distance2:
                if chunk_key in self.lod_entities:
                    lod_chunks.add(chunk_key)
                else:
                    # LOD生成待ちは通常Entityで穴を防ぐ。
                    near_chunks.add(chunk_key)

        for block in self.boxes:
            x, y, z = block.block_position
            chunk_key = self._chunk_key(x, z)
            if chunk_key in protected_chunks:
                should_enable = True
            else:
                entity_vertical_distance = 6 if high_altitude else vertical_distance
                should_enable = (
                    chunk_key in near_chunks
                    and abs(y - player_y) < entity_vertical_distance
                )
            should_be_visible = (
                should_enable
                and (chunk_key not in lod_chunks or self._is_transparent(block))
            )
            if block.enabled != should_enable:
                block.enabled = should_enable
            if block.visible != should_be_visible:
                block.visible = should_be_visible

        for chunk_key, entities in self.lod_entities.items():
            should_enable = chunk_key in lod_chunks
            for entity in entities:
                if entity.enabled != should_enable:
                    entity.enabled = should_enable

        self.visible_lod_chunks = set(lod_chunks)
        self.lod_enabled = bool(lod_chunks)

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
        for entry in data['blocks']:
            bx, by, bz, block_id = entry[:4]
            orientation = entry[4] if len(entry) > 4 else 'y'
            self.place_block(bx, by, bz, block_id, orientation=orientation)

        player_entity.position = tuple(data['player'])
        print(f'loaded: {self.save_path}, boxes count={len(self.boxes)}')
