import json
import os
from datetime import datetime
from ursina import Button, destroy, scene,BoxCollider,Entity
from block_types import BLOCK_TYPES
from config import (SAVE_VERSION, SAND_FALL_SPEED, SAND_START_DELAY,
                    VOID_Y, WORLD_SIZE)
from custom_mesh import make_face_atlas_cube


class World:
    def __init__(self, save_path):
        self.save_path = save_path
        self.boxes = []
        self._blocks_by_position = {}
        self._falling_sand = set()
        self._sand_pending = {}
        self._sand_accumulator = 0.0

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
        self._blocks_by_position[b.block_position] = b
        if name == 'Sand':
            below = self._blocks_by_position.get((int(x), int(y) - 1, int(z)))
            if below is None:
                self._start_sand_fall(b)
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
            position = getattr(block, 'block_position', None)
            self.boxes.remove(block)
            self._falling_sand.discard(block)
            self._sand_pending.pop(block, None)
            if position and self._blocks_by_position.get(position) is block:
                del self._blocks_by_position[position]
            destroy(block)
            if position:
                self._start_sand_above_position(position)

    def _has_solid_support(self, block):
        x, y, z = block.block_position
        below = self._blocks_by_position.get((x, y - 1, z))
        return below is not None and below not in self._falling_sand

    def _start_sand_fall(self, block, delay=SAND_START_DELAY):
        if block.block_type != 5 or block in self._falling_sand:
            return
        if delay > 0:
            current_delay = self._sand_pending.get(block)
            if current_delay is None or delay < current_delay:
                self._sand_pending[block] = delay
            return
        block.collider = None
        block._sand_y = block.block_position[1]
        self._falling_sand.add(block)
        self._queue_sand_above(block)

    def _queue_sand_above(self, block, delay=0.08):
        x, y, z = block.block_position
        self._queue_sand_above_position((x, y, z), delay)

    def _start_sand_above_position(self, position):
        x, y, z = position
        y += 1
        while y < WORLD_SIZE * 4:
            above = self._blocks_by_position.get((x, y, z))
            if above is None:
                y += 1
                continue
            if above.block_type == 5:
                self._start_sand_fall(above)
            return

    def _queue_sand_above_position(self, position, delay=0.08):
        x, y, z = position
        y += 1
        while y < WORLD_SIZE * 4:
            above = self._blocks_by_position.get((x, y, z))
            if above is None:
                y += 1
                continue
            if above.block_type == 5:
                current_delay = self._sand_pending.get(above)
                if current_delay is None or delay < current_delay:
                    self._sand_pending[above] = delay
            return

    def update_sand(self, dt):
        if not self._falling_sand and not self._sand_pending:
            return

        self._sand_accumulator += dt
        if self._sand_accumulator < 0.05:
            return
        step_dt = min(self._sand_accumulator, 0.2)
        self._sand_accumulator = 0.0
        fall_distance = SAND_FALL_SPEED * step_dt

        for block, delay in tuple(self._sand_pending.items()):
            delay -= step_dt
            if block not in self.boxes:
                del self._sand_pending[block]
            elif delay <= 0:
                del self._sand_pending[block]
                self._start_sand_fall(block, delay=0)
            else:
                self._sand_pending[block] = delay

        for block in tuple(self._falling_sand):
            if block.y < VOID_Y:
                self.remove_block(block)
                continue

            x, _, z = block.block_position
            current_y = block._sand_y
            below = self._blocks_by_position.get((x, current_y - 1, z))
            if below is not None and below not in self._falling_sand:
                block.y = current_y
                block.collider = 'box'
                self._falling_sand.remove(block)
                continue

            block.y -= fall_distance
            while block.y <= current_y - 1:
                old_position = block.block_position
                current_y -= 1
                new_position = (x, current_y, z)
                if self._blocks_by_position.get(old_position) is block:
                    del self._blocks_by_position[old_position]
                self._blocks_by_position[new_position] = block
                block.block_position = new_position
                block._sand_y = current_y

                below = self._blocks_by_position.get((x, current_y - 1, z))
                if below is not None and below not in self._falling_sand:
                    block.y = current_y
                    block.collider = 'box'
                    self._falling_sand.remove(block)
                    break

    def clear(self):
        for block in self.boxes:
            destroy(block)
        self.boxes.clear()
        self._blocks_by_position.clear()
        self._falling_sand.clear()
        self._sand_pending.clear()
        self._sand_accumulator = 0.0

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
