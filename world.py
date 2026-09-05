import json
import os
from datetime import datetime
from ursina import Button, destroy, scene,BoxCollider,Entity
from block_types import BLOCK_TYPES
from config import SAVE_VERSION, WORLD_SIZE
from custom_mesh import make_face_atlas_cube


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        self.boxes = []

    def place_block(self, x, y, z, block_id, orientation='y'):
        name, col, tex_info = BLOCK_TYPES[block_id]
        if isinstance(tex_info, dict) and 'atlas' in tex_info:
            b = Entity(
                color=col,
                model=make_face_atlas_cube(orientation),
                position=(x, y - 0.5, z),
                texture=tex_info['atlas'],
                parent=scene,
                collider='box',
            )
            b.custom_mesh = True
            b.orientation = orientation
        else:
            b = Entity(
                color=col,
                model='cube',
                position=(x, y, z),
                texture=tex_info,
                parent=scene,
                origin_y=0.5,
                collider='box',
            )
            b.custom_mesh = False
            b.orientation = 'y'

        if b.texture:
            b.texture.filtering = None
        b.block_type = block_id

        if name == 'Glass':
            from panda3d.core import TransparencyAttrib

            b.setTransparency(TransparencyAttrib.M_alpha)
            b.set_bin('transparent', 30)
            b.setDepthWrite(False)

        b.block_position = (int(x), int(y), int(z))
        self.boxes.append(b)
        return b
        name, col, tex_info = BLOCK_TYPES[block_id]

        if isinstance(tex_info, dict) and 'atlas' in tex_info:
            b = Entity(
                color=col,
                model=make_face_atlas_cube(orientation),
                position=(x, y - 0.5, z),
                texture=tex_info['atlas'],
                parent=scene,
                collider='box',
            )
            b.custom_mesh = True
            b.orientation = orientation
        else:
            b = Entity(
                color=col,
                model='cube',
                position=(x, y, z),
                texture=tex_info,
                parent=scene,
                origin_y=0.5,
                collider='box',
            )
            b.custom_mesh = False
            b.orientation = 'y'

        if b.texture:
            b.texture.filtering = None
        b.block_type = block_id
        
        if name == 'Glass':
            from panda3d.core import TransparencyAttrib
            b.setTransparency(TransparencyAttrib.M_alpha)
            b.set_bin('transparent', 30)

            self.boxes.append(b)
            return b


    def remove_block(self, block):
        if block in self.boxes:
            self.boxes.remove(block)
            destroy(block)

    def generate_flat(self):
        for i in range(WORLD_SIZE):
            for j in range(WORLD_SIZE):
                self.place_block(j, 0, i, 0)

    def save(self, player_entity):
        data = {
            'version': SAVE_VERSION,
            'name': os.path.basename(self.save_path)[:-5],
            'last_played': datetime.now().isoformat(),
            'player': [player_entity.x, player_entity.y, player_entity.z],
            'blocks': [self._block_to_save(b) for b in self.boxes],
        }
        with open(self.save_path, 'w') as f:
            json.dump(data, f)
        print(f'saved: {self.save_path}')


    def _block_to_save(self, b):
        _, _, tex_info = BLOCK_TYPES[b.block_type]
        block_x, block_y, block_z = getattr(
            b, 'block_position', (b.x, b.y, b.z))
        if isinstance(tex_info, dict):
            return [int(block_x), int(block_y), int(block_z), b.block_type,
                    getattr(b, 'orientation', 'y')]
        return [int(block_x), int(block_y), int(block_z), b.block_type,
                getattr(b, 'orientation', 'y')]



    def load(self, player_entity):
        with open(self.save_path) as f:
            data = json.load(f)
        for entry in data['blocks']:
            if len(entry) == 4:
                bx, by, bz, bid = entry
                orientation = 'y'
            else:
                bx, by, bz, bid, orientation = entry
            self.place_block(bx, by, bz, bid, orientation=orientation)
        px, py, pz = data['player']
        player_entity.position = (px, py, pz)
        print(f'loaded: {self.save_path}, boxes count={len(self.boxes)}')
