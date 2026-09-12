import json
import os
import secrets
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from panda3d.core import TransparencyAttrib, Texture
from ursina import Entity, Mesh, Vec3, color, destroy, scene

from block_types import BLOCK_TYPES
from config import SAVE_VERSION, WORLD_SIZE, TEMPLATE_PATH
from custom_mesh import make_face_atlas_cube
from terrain_generator import (
    GENERATOR_ID, TREE_GENERATOR_ID,
    iter_grassland_blocks, iter_grassland_v2_blocks, surface_height,
)


LOD_CHUNK_SIZE = 10
SAND_BLOCK_ID = 5
TEMPLATE_GENERATOR_ID = 'template_v1'

# ジャンプ設置などで同じチャンクへ連続して変更が入っている間は
# LOD再構築（全ブロック走査＋Mesh再生成という重い処理）を遅らせる。
# 自分がいる/建築中のチャンクは常に保護チャンクとして通常描画され
# LODは使われないため、この遅延は見た目に影響しない。
LOD_REBUILD_DEBOUNCE = 0.3
LOD_BREAK_REBUILD_DELAY = 0.05
# 連続変更が長く続いた場合でも、最終的には反映されるようにする上限。
LOD_REBUILD_MAX_WAIT = 5.0

# 高所LOD（遠景の地面を個別Entityではなく結合メッシュに切り替える）が
# 発動する高度差。以前はrender_distanceに連動していて発動が遅く、
# 切り替わる前に個別ブロックが大量に見えてFPSが落ちていたため、
# render_distanceに関わらず固定値にしている。値を下げるほど早く
# LODに切り替わり、上空でのFPSは安定するが、切り替わりの境界が
# プレイヤーに近くなるため見た目の粗さが分かりやすくなる。
HIGH_ALTITUDE_ENABLE_HEIGHT = 14
HIGH_ALTITUDE_DISABLE_HEIGHT = 9


@dataclass(frozen=True, slots=True)
class BlockData:
    """描画Entityから独立した軽量な論理ブロック情報。"""
    block_type: int
    orientation: str = 'y'


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        self.seed = secrets.randbits(64)
        self.boxes = []
        # 既存互換: Entity参照。Stage 3CまではDDA、選択枠、粒子で使用する。
        self.blocks_by_position = {}
        # Stage 3C-3: Glass等、個別描画が必要なブロックだけ保持する。
        self.block_entities_by_position = {}
        # 新しい正規データ: 描画方式やColliderに依存しない論理ブロック情報。
        self.block_data_by_position = {}
        # 基本地形とプレイヤー変更の差分。Phase 2Aでは全blocks保存も維持する。
        self.generated_positions = set()
        self.placed_blocks = {}
        self.removed_blocks = set()
        self._loading_world = False
        self.generator = None
        self.sand_positions = set()
        # チャンクごとのブロック座標索引
        self.blocks_by_chunk = defaultdict(set)

        # 遠距離表示用。チャンクごと、ブロック種類ごとに上面を結合する。
        self.lod_entities = {}
        self.dirty_lod_chunks = set()
        self.urgent_lod_chunks = set()
        # チャンクごとの dirty 化タイムスタンプ（連続変更のデバウンス用）
        self._lod_dirty_first_at = {}
        self._lod_dirty_last_at = {}
        # 直前フレームで再構築をスキップしていたチャンク（＝滞在中チャンク）
        self._previous_active_chunk_keys = set()
        self.lod_enabled = False
        self._high_altitude_lod = False
        self.visible_lod_chunks = set()
        # 保護範囲外で不透明ブロックを結合メッシュ表示するチャンク。
        self.combined_mesh_chunks = set()
        # Colliderを有効にするプレイヤー周辺チャンク。
        self.active_collider_chunks = set()

    @staticmethod
    def _position_key(x, y, z):
        return int(round(x)), int(round(y)), int(round(z))

    @staticmethod
    def _chunk_key(x, z):
        return int(x) // LOD_CHUNK_SIZE, int(z) // LOD_CHUNK_SIZE

    def chunk_key_at(self, x, z):
        """呼び出し側（main.py）がプレイヤー位置からチャンクキーを求めるための公開API。"""
        return self._chunk_key(x, z)

    def update_active_colliders(self, player_x, player_z):
        """Stage 3C-3ではプレイヤー衝突は論理データを使うため処理不要。"""
        self.active_collider_chunks = self.protected_chunk_keys(player_x, player_z)
        return False

    def get_block(self, x, y, z):
        """論理ブロック情報を返す。個別描画Entityには依存しない。"""
        return self.block_data_by_position.get(self._position_key(x, y, z))

    def get_block_data(self, x, y, z):
        """描画Entityに依存しない論理ブロック情報を返す。"""
        return self.block_data_by_position.get(self._position_key(x, y, z))

    def has_block(self, x, y, z):
        return self._position_key(x, y, z) in self.block_data_by_position

    def place_block(self, x, y, z, block_id, orientation='y', generated=False):
        position = self._position_key(x, y, z)
        existing = self.block_data_by_position.get(position)
        if existing is not None:
            return existing

        name, block_color, texture_info = BLOCK_TYPES[block_id]
        orientation = orientation if orientation in ('x', 'y', 'z') else 'y'
        block_data = BlockData(int(block_id), orientation)
        chunk_key = self._chunk_key(position[0], position[2])

        self.block_data_by_position[position] = block_data
        self.blocks_by_position[position] = block_data
        self.blocks_by_chunk[chunk_key].add(position)

        if generated or self._loading_world:
            self.generated_positions.add(position)
        else:
            self.placed_blocks[position] = block_data
            self.removed_blocks.discard(position)
        if block_id == SAND_BLOCK_ID:
            self.sand_positions.add(position)

        # 透明ブロックだけは描画順制御のため個別Entityを維持する。
        if name == 'Glass' or texture_info is None:
            if isinstance(texture_info, dict) and 'atlas' in texture_info:
                entity = Entity(
                    color=block_color,
                    model=make_face_atlas_cube(orientation),
                    position=(position[0], position[1] - 0.5, position[2]),
                    texture=texture_info['atlas'],
                    parent=scene,
                    collider=None,
                )
                entity.custom_mesh = True
            else:
                entity = Entity(
                    color=block_color,
                    model='cube',
                    position=position,
                    texture=texture_info,
                    parent=scene,
                    origin_y=0.5,
                    collider=None,
                )
                entity.custom_mesh = False
            entity.orientation = orientation
            entity.block_type = block_id
            entity.block_position = position
            if entity.texture:
                entity.texture.filtering = None
            if name == 'Glass':
                entity.setTransparency(TransparencyAttrib.M_alpha)
                entity.set_bin('transparent', 30)
                entity.setDepthWrite(False)
            self.boxes.append(entity)
            self.block_entities_by_position[position] = entity

        # 個別の不透明Entityがないため、設置後の結合メッシュを優先更新する。
        # チャンク境界の場合は隣接チャンクも更新する。
        for affected_chunk in self._affected_chunk_keys(position):
            self._mark_lod_dirty(affected_chunk, urgent=True)
        return block_data

    def remove_block_at(self, x, y, z):
        position = self._position_key(x, y, z)
        if position not in self.block_data_by_position:
            return False

        was_generated = position in self.generated_positions
        was_player_placed = position in self.placed_blocks
        if not self._loading_world:
            if was_player_placed:
                # 設置してから破壊した変更は相殺する。
                self.placed_blocks.pop(position, None)
            elif was_generated:
                self.removed_blocks.add(position)

        self.block_data_by_position.pop(position, None)
        self.blocks_by_position.pop(position, None)
        self.sand_positions.discard(position)

        entity = self.block_entities_by_position.pop(position, None)
        if entity is not None:
            try:
                self.boxes.remove(entity)
            except ValueError:
                pass
            destroy(entity)

        chunk_key = self._chunk_key(position[0], position[2])
        positions = self.blocks_by_chunk.get(chunk_key)
        if positions is not None:
            positions.discard(position)
            if not positions:
                self.blocks_by_chunk.pop(chunk_key, None)
        for affected_chunk in self._affected_chunk_keys(position):
            self._mark_lod_dirty(affected_chunk, urgent=True)
        return True

    def remove_block(self, block):
        """既存呼び出し向け互換API。"""
        position = getattr(block, 'block_position', None)
        if position is None:
            for key, value in self.block_data_by_position.items():
                if value is block:
                    position = key
                    break
        if position is None:
            return False
        return self.remove_block_at(*position)

    def _mark_lod_dirty(self, chunk_key, urgent=False):
        now = monotonic()
        self.dirty_lod_chunks.add(chunk_key)
        if urgent:
            self.urgent_lod_chunks.add(chunk_key)
        if chunk_key not in self._lod_dirty_first_at:
            self._lod_dirty_first_at[chunk_key] = now
        self._lod_dirty_last_at[chunk_key] = now

    def _affected_chunk_keys(self, position):
        """境界面を共有する隣接チャンクも返す。"""
        x, _y, z = position
        chunk_x, chunk_z = self._chunk_key(x, z)
        result = {(chunk_x, chunk_z)}
        local_x = x - chunk_x * LOD_CHUNK_SIZE
        local_z = z - chunk_z * LOD_CHUNK_SIZE
        if local_x == 0:
            result.add((chunk_x - 1, chunk_z))
        elif local_x == LOD_CHUNK_SIZE - 1:
            result.add((chunk_x + 1, chunk_z))
        if local_z == 0:
            result.add((chunk_x, chunk_z - 1))
        elif local_z == LOD_CHUNK_SIZE - 1:
            result.add((chunk_x, chunk_z + 1))
        return result

    def clear(self):
        for block in self.boxes:
            destroy(block)
        self.boxes.clear()
        self.blocks_by_position.clear()
        self.block_entities_by_position.clear()
        self.block_data_by_position.clear()
        self.generated_positions.clear()
        self.placed_blocks.clear()
        self.removed_blocks.clear()
        self._loading_world = False
        self.sand_positions.clear()
        self.blocks_by_chunk.clear()
        self.clear_lod()

    def clear_lod(self):
        for entities in self.lod_entities.values():
            for entity in entities:
                destroy(entity)
        self.lod_entities.clear()
        self.dirty_lod_chunks.clear()
        self.urgent_lod_chunks.clear()
        self._lod_dirty_first_at.clear()
        self._lod_dirty_last_at.clear()
        self._previous_active_chunk_keys.clear()
        self.lod_enabled = False
        self._high_altitude_lod = False
        self.visible_lod_chunks.clear()
        self.combined_mesh_chunks.clear()
        self.active_collider_chunks.clear()

    def dispose(self):
        self.clear()

    def generate_flat(self):
        self.generator = 'flat_v1'
        for z in range(WORLD_SIZE):
            for x in range(WORLD_SIZE):
                self.place_block(x, 0, z, 0, generated=True)

    def generate_grassland(self):
        self.generator = TREE_GENERATOR_ID
        for x, y, z, block_id, orientation in iter_grassland_v2_blocks(
            self.seed, WORLD_SIZE
        ):
            self.place_block(
                x, y, z, block_id,
                orientation=orientation,
                generated=True,
            )

    def terrain_surface_y(self, x, z):
        if self.generator in (GENERATOR_ID, TREE_GENERATOR_ID):
            return surface_height(self.seed, int(round(x)), int(round(z)), WORLD_SIZE)
        column = [y for bx, y, bz in self.block_data_by_position if bx == round(x) and bz == round(z)]
        return max(column) if column else 0

    def generate_template(self):
        template_path = Path(TEMPLATE_PATH)
        if not template_path.exists():
            return False
        with template_path.open(encoding='utf-8') as template_file:
            template = json.load(template_file)
        self.generator = TEMPLATE_GENERATOR_ID
        self._loading_world = True
        for entry in template.get('blocks', []):
            if len(entry) >= 4:
                self.place_block(
                    *entry[:3], entry[3],
                    orientation=entry[4] if len(entry) > 4 else 'y',
                    generated=True,
                )
        self._loading_world = False
        return True

    def _generate_baseline(self, generator):
        if generator == TEMPLATE_GENERATOR_ID:
            return self.generate_template()
        if generator == TREE_GENERATOR_ID:
            self.generator = TREE_GENERATOR_ID
            for x, y, z, block_id, orientation in iter_grassland_v2_blocks(
                self.seed, WORLD_SIZE
            ):
                self.place_block(
                    x, y, z, block_id,
                    orientation=orientation,
                    generated=True,
                )
            return True
        if generator == GENERATOR_ID:
            self.generator = GENERATOR_ID
            for x, y, z, block_id, orientation in iter_grassland_blocks(
                self.seed, WORLD_SIZE
            ):
                self.place_block(
                    x, y, z, block_id,
                    orientation=orientation,
                    generated=True,
                )
            return True
        if generator == 'flat_v1':
            self.generate_flat()
            return True
        return False

    def _apply_saved_differences(self, placed, removed):
        self._loading_world = True
        for entry in removed:
            if len(entry) >= 3:
                self.remove_block_at(*entry[:3])
        for entry in placed:
            if len(entry) >= 4:
                self.remove_block_at(*entry[:3])
                self.place_block(*entry[:3], entry[3],
                    orientation=entry[4] if len(entry) > 4 else 'y')
        self._loading_world = False
        self.placed_blocks = {
            self._position_key(*e[:3]): BlockData(int(e[3]), e[4] if len(e) > 4 else 'y')
            for e in placed if len(e) >= 4
        }
        self.removed_blocks = {
            self._position_key(*e[:3]) for e in removed if len(e) >= 3
        }
        self.generated_positions.difference_update(self.placed_blocks)

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

    def build_initial_meshes(self):
        """初期読込後、全チャンクの不透明メッシュを一括生成する。"""
        for chunk_key in tuple(self.blocks_by_chunk):
            self._rebuild_lod_chunk(chunk_key)
        self.dirty_lod_chunks.clear()
        self._lod_dirty_first_at.clear()
        self._lod_dirty_last_at.clear()

    def rebuild_dirty_lod(self, max_chunks=1, active_chunk_keys=None):
        # LOD再生成を複数フレームへ分散して、一括停止を避ける。
        # さらに、連続してブロックを設置/破壊しているチャンクは
        # 変更が落ち着くまで再構築を遅らせる（デバウンス）。
        # 再構築中のチャンクは自分の足元＝保護チャンクであることが多く、
        # その間はLODが使われないため、遅らせても見た目には影響しない。
        #
        # active_chunk_keys（プレイヤーが今いるチャンクなど）に含まれる
        # チャンクは、そこに留まっている間は LOD_REBUILD_MAX_WAIT による
        # 強制再構築も含めて完全にスキップする。建築中に定期的な重い
        # 再構築スパイクが挟まってfpsが谷落ちするのを防ぐため。
        active_chunk_keys = set(active_chunk_keys or ())

        # チャンクを離れた瞬間、溜まっていた変更が即座に（同じフレームで）
        # 重い再構築として発火すると、それが移動時のラグとして感じられる。
        # 離脱を検知したら「今dirtyになった」ものとしてタイマーをリセットし、
        # 通常のデバウンス（LOD_REBUILD_DEBOUNCE秒）を必ず経由させる。
        now = monotonic()
        left_chunks = self._previous_active_chunk_keys - active_chunk_keys
        for chunk_key in left_chunks:
            if chunk_key in self.dirty_lod_chunks:
                self._lod_dirty_first_at[chunk_key] = now
                self._lod_dirty_last_at[chunk_key] = now
        self._previous_active_chunk_keys = active_chunk_keys

        if not self.dirty_lod_chunks:
            return

        rebuilt = 0

        ordered_chunks = (
            tuple(self.urgent_lod_chunks)
            + tuple(self.dirty_lod_chunks - self.urgent_lod_chunks)
        )
        for chunk_key in ordered_chunks:
            if rebuilt >= max_chunks:
                break
            if chunk_key in active_chunk_keys:
                continue

            last_at = self._lod_dirty_last_at.get(chunk_key, now)
            first_at = self._lod_dirty_first_at.get(chunk_key, now)
            delay = (
                LOD_BREAK_REBUILD_DELAY
                if chunk_key in self.urgent_lod_chunks
                else LOD_REBUILD_DEBOUNCE
            )
            settled = (now - last_at) >= delay
            timed_out = (now - first_at) >= LOD_REBUILD_MAX_WAIT
            if not settled and not timed_out:
                continue

            self.dirty_lod_chunks.discard(chunk_key)
            self.urgent_lod_chunks.discard(chunk_key)
            self._lod_dirty_first_at.pop(chunk_key, None)
            self._lod_dirty_last_at.pop(chunk_key, None)
            self._rebuild_lod_chunk(chunk_key)
            rebuilt += 1

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
            block = self.block_data_by_position.get(position)
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

        # Stage 3C-3では不透明ブロックの個別Entityは存在しない。
        # 新しい結合メッシュを同じフレームで有効化するだけでよい。
        if chunk_key in self.combined_mesh_chunks:
            for entity in new_entities:
                entity.enabled = True
            self.visible_lod_chunks.add(chunk_key)

    PROTECTION_RADIUS = 2

    def protected_chunk_keys(self, player_x, player_z):
        """足元を中心とした半径PROTECTION_RADIUSブロックが触れるチャンク集合。
        通常は1チャンク、境界付近でも最大4チャンクに制限される。
        update_visibility()（表示判定）とrebuild_dirty_lod()の
        active_chunk_keys（再構築の一時停止対象）の両方で、
        必ず同じ集合を使うこと。ズレると「保護されているのに
        再構築（重いフルスキャン+Mesh再生成）は止まらない」チャンクが
        生まれ、境界付近で建築するとラグの原因になる。
        """
        radius = self.PROTECTION_RADIUS
        min_chunk_x, min_chunk_z = self._chunk_key(
            player_x - radius, player_z - radius,
        )
        max_chunk_x, max_chunk_z = self._chunk_key(
            player_x + radius, player_z + radius,
        )
        return {
            (chunk_x, chunk_z)
            for chunk_x in range(min_chunk_x, max_chunk_x + 1)
            for chunk_z in range(min_chunk_z, max_chunk_z + 1)
        }

    def update_visibility(self, player_x, player_y, player_z,
                          vertical_distance, render_distance):
        chunk_radius = LOD_CHUNK_SIZE * 0.75
        lod_distance = render_distance + chunk_radius
        lod_distance2 = lod_distance * lod_distance
        protected_chunks = self.protected_chunk_keys(player_x, player_z)

        nearby_chunks = set()
        desired_mesh_chunks = set()
        fallback_chunks = set()
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

            if distance2 <= lod_distance2:
                # Stage 3C-3では不透明な個別Entityが存在しないため、
                # プレイヤー周辺を含む全チャンクを結合メッシュで描画する。
                desired_mesh_chunks.add(chunk_key)
                if chunk_key not in self.lod_entities:
                    fallback_chunks.add(chunk_key)

        self.combined_mesh_chunks = desired_mesh_chunks
        visible_mesh_chunks = desired_mesh_chunks - fallback_chunks

        for block in self.boxes:
            x, _y, z = block.block_position
            chunk_key = self._chunk_key(x, z)
            should_enable = (
                chunk_key in protected_chunks
                or chunk_key in fallback_chunks
                or chunk_key in visible_mesh_chunks
            )
            if block.enabled != should_enable:
                block.enabled = should_enable
            if block.visible != should_enable:
                block.visible = should_enable

        for chunk_key, entities in self.lod_entities.items():
            should_enable = chunk_key in visible_mesh_chunks
            for entity in entities:
                if entity.enabled != should_enable:
                    entity.enabled = should_enable

        self.visible_lod_chunks = set(visible_mesh_chunks)
        self.lod_enabled = bool(visible_mesh_chunks)

    def get_chunk_positions(self, chunk_x, chunk_z):
        return tuple(self.blocks_by_chunk.get((chunk_x, chunk_z), ()))

    def get_chunk_blocks(self, chunk_x, chunk_z):
        return tuple(
            self.block_data_by_position[position]
            for position in self.get_chunk_positions(chunk_x, chunk_z)
            if position in self.block_data_by_position
        )

    def loaded_chunk_keys(self):
        return tuple(self.blocks_by_chunk.keys())

    def validate_block_data(self):
        positions = set(self.block_data_by_position)
        return {
            'ok': positions == set(self.blocks_by_position),
            'logical_blocks': len(positions),
            'individual_entities': len(self.boxes),
        }

    def debug_stats(self, player_x=None, player_z=None):
        """デバッグオーバーレイ表示用のチャンク/LOD統計。"""
        visible_blocks = sum(1 for block in self.boxes if block.visible)
        stats = {
            'chunks_loaded': len(self.blocks_by_chunk),
            'lod_built': len(self.lod_entities),
            'lod_dirty': len(self.dirty_lod_chunks),
            'lod_visible': len(self.visible_lod_chunks),
            'high_altitude': self._high_altitude_lod,
            'visible_blocks': visible_blocks,
            'block_data': len(self.block_data_by_position),
            'protected_chunks': None,
            'individual_entities': len(self.boxes),
            'mesh_entities': sum(
                len(entities)
                for entities in self.lod_entities.values()
            ),
        }
        if player_x is not None and player_z is not None:
            stats['protected_chunks'] = len(
                self.protected_chunk_keys(player_x, player_z)
            )
        return stats

    def save(self, player_entity):
        data = {
            'version': SAVE_VERSION,
            'seed': self.seed,
            'name': os.path.basename(self.save_path)[:-5],
            'last_played': datetime.now().isoformat(),
            'player': [player_entity.x, player_entity.y, player_entity.z],
            'generator': self.generator,
            'placed_blocks': [
                [x, y, z, data.block_type, data.orientation]
                for (x, y, z), data in self.placed_blocks.items()
            ],
            'removed_blocks': [
                [x, y, z]
                for (x, y, z) in sorted(self.removed_blocks)
            ],
        }
        if self.generator is None:
            data['blocks'] = [
                [x, y, z, block.block_type, block.orientation]
                for (x, y, z), block in self.block_data_by_position.items()
            ]
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

        self.seed = int(data.get('seed', secrets.randbits(64)))

        self.clear()
        generator = data.get('generator')
        placed = data.get('placed_blocks', [])
        removed = data.get('removed_blocks', [])
        if generator and self._generate_baseline(generator):
            self._apply_saved_differences(placed, removed)
        else:
            self.generator = None
            self._loading_world = True
            for entry in data.get('blocks', []):
                if len(entry) >= 4:
                    self.place_block(*entry[:3], entry[3],
                        orientation=entry[4] if len(entry) > 4 else 'y', generated=True)
            self._loading_world = False
            self.placed_blocks = {
                self._position_key(*e[:3]): BlockData(int(e[3]), e[4] if len(e) > 4 else 'y')
                for e in placed if len(e) >= 4
            }
            self.removed_blocks = {
                self._position_key(*e[:3]) for e in removed if len(e) >= 3
            }
            self.generated_positions.difference_update(self.placed_blocks)

        player_entity.position = tuple(data['player'])
        print(f'loaded: {self.save_path}, boxes count={len(self.boxes)}')