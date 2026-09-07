import json
import os
from datetime import datetime

from panda3d.core import TransparencyAttrib
from ursina import Entity, destroy, scene

from block_types import BLOCK_TYPES
from config import SAVE_VERSION, WORLD_SIZE
from custom_mesh import make_face_atlas_cube


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        # boxesは既存コードとの互換用。座標検索は辞書を使う。
        self.boxes = []
        self.blocks_by_position = {}

    @staticmethod
    def _position_key(x, y, z):
        return int(round(x)), int(round(y)), int(round(z))

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

        self.boxes.append(block)
        self.blocks_by_position[position] = block
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

        destroy(target)
        return True

    def clear(self):
        for block in self.boxes:
            destroy(block)
        self.boxes.clear()
        self.blocks_by_position.clear()

    def generate_flat(self):
        for z in range(WORLD_SIZE):
            for x in range(WORLD_SIZE):
                self.place_block(x, 0, z, 0)

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
