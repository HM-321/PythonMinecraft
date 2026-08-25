import time
from ursina import Entity, Text, camera, color, window
from block_types import BLOCK_TYPES
import os
import psutil


class Crosshair:
    def __init__(self):
        aspect = window.aspect_ratio
        self.root = Entity(parent=camera.ui)
        Entity(parent=self.root, model='quad', color=color.white,
               scale=(0.015, 0.003), z=-1)
        Entity(parent=self.root, model='quad', color=color.white,
               scale=(0.003, 0.015), z=-1)


from block_types import BLOCK_TYPES, HOTBAR_ORDER

class SelectionFrame:
    def __init__(self):
        self.root = Entity(enabled=False)
        _v, _t = 0.501, 0.005
        c = color.black

        edges = [
            ((0, -_v, -_v), (2 * _v + _t, _t, _t)),
            ((0, -_v,  _v), (2 * _v + _t, _t, _t)),
            ((-_v, -_v, 0), (_t, _t, 2 * _v + _t)),
            ((_v, -_v, 0),  (_t, _t, 2 * _v + _t)),
            ((0, _v, -_v),  (2 * _v + _t, _t, _t)),
            ((0, _v,  _v),  (2 * _v + _t, _t, _t)),
            ((-_v, _v, 0),  (_t, _t, 2 * _v + _t)),
            ((_v, _v, 0),   (_t, _t, 2 * _v + _t)),
            ((-_v, 0, -_v), (_t, 2 * _v + _t, _t)),
            ((_v, 0, -_v),  (_t, 2 * _v + _t, _t)),
            ((-_v, 0,  _v), (_t, 2 * _v + _t, _t)),
            ((_v, 0,  _v),  (_t, 2 * _v + _t, _t)),
        ]
        for pos, sc in edges:
            Entity(parent=self.root, model='cube', color=c,
                   position=pos, scale=sc)

    def show_at(self, block):
        self.root.enabled = True
        if getattr(block, 'custom_mesh', False):
            self.root.position = (block.x, block.y, block.z)
        else:
            self.root.position = (block.x, block.y - 0.5, block.z)

    def hide(self):
        self.root.enabled = False



class Hotbar:
    def __init__(self):
        self.selected = 0    # BLOCK_TYPESのインデックス (0 = Grass)
        SLOT, GAP, BORDER = 0.05, 0.01, 0.004
        self.step_x = SLOT + GAP
        self.SLOT = SLOT

        self.root = Entity(parent=camera.ui, position=(0, -0.45))
        self._slot_x = {}   # {block_id: x} の辞書に変更

        for slot_idx, block_id in enumerate(HOTBAR_ORDER):
            name, col, tex_info = BLOCK_TYPES[block_id]
            x = (slot_idx - (len(HOTBAR_ORDER) - 1) / 2) * self.step_x
            self._slot_x[block_id] = x

            # アイコンテクスチャ決定
            if isinstance(tex_info, dict):
                icon_tex = tex_info.get('icon', tex_info.get('atlas'))
            else:
                icon_tex = tex_info

            Entity(parent=self.root, model='quad', color=color.dark_gray,
                position=(x, 0, 0.01), scale=(SLOT, SLOT))
            Entity(parent=self.root, model='quad', color=col, texture=icon_tex,
                position=(x, 0, 0), scale=(SLOT * 0.8, SLOT * 0.8))

        self.selector = Entity(parent=self.root)
        Entity(parent=self.selector, model='quad', color=color.yellow,
               position=(0, SLOT * 0.55), scale=(SLOT * 1.15, BORDER))
        Entity(parent=self.selector, model='quad', color=color.yellow,
               position=(0, -SLOT * 0.55), scale=(SLOT * 1.15, BORDER))
        Entity(parent=self.selector, model='quad', color=color.yellow,
               position=(-SLOT * 0.55, 0), scale=(BORDER, SLOT * 1.15))
        Entity(parent=self.selector, model='quad', color=color.yellow,
               position=(SLOT * 0.55, 0), scale=(BORDER, SLOT * 1.15))

        self.block_text = Text(
            text='', parent=self.root,
            position=(0, SLOT * 0.75),
            origin=(0, 0),
            scale=1.5,
            color=color.white,
        )
        self.last_selection_time = 0
        self._refresh()

    def set_selected(self, hotbar_idx):
        """hotbar_idx = 0〜8 (ホットバー上の位置)"""
        if 0 <= hotbar_idx < len(HOTBAR_ORDER):
            self.selected = HOTBAR_ORDER[hotbar_idx]
            self._refresh()

    def cycle(self, delta):
        """ホットバー上の位置を巡回"""
        current_hotbar_idx = HOTBAR_ORDER.index(self.selected)
        new_idx = (current_hotbar_idx + delta) % len(HOTBAR_ORDER)
        self.selected = HOTBAR_ORDER[new_idx]
        self._refresh()

    def _refresh(self):
        self.selector.x = self._slot_x[self.selected]
        self.block_text.text = BLOCK_TYPES[self.selected][0]
        self.last_selection_time = time.time()

    def maybe_hide(self):
        if time.time() - self.last_selection_time > 2.0:
            self.block_text.text = ''


    def hide(self):
        self.root.enabled = False

    def show_at(self, block):
        self.root.enabled = True
        # カスタムメッシュのブロックは既に中心Yなので補正不要
        if getattr(block, 'custom_mesh', False):
            self.root.position = (block.x, block.y, block.z)
        else:
            self.root.position = (block.x, block.y - 0.5, block.z)

class DebugOverlay:
    def __init__(self):
        self.root = Entity(parent=camera.ui, enabled=False)
        x_pos = -window.aspect_ratio * 0.5 + 0.02
        self.text = Text(
            parent=self.root,
            text='',
            position=(x_pos, 0.48),
            origin=(-0.5, 0.5),
            scale=0.9,
            color=color.white,
            background=False,
        )
        self._fps_accum = 0
        self._fps_frames = 0
        self._fps = 0
        self._process = psutil.Process(os.getpid())   # ← 追加
        self._mem_mb = 0
        self._mem_counter = 0

    def toggle(self):
        self.root.enabled = not self.root.enabled

    def update(self, dt, player, hotbar, world, gravity_on):
        if not self.root.enabled:
            return

        # FPS
        self._fps_accum += dt
        self._fps_frames += 1
        if self._fps_accum >= 0.5:
            self._fps = self._fps_frames / self._fps_accum
            self._fps_accum = 0
            self._fps_frames = 0

        # メモリ（1秒に1回だけ計測、psutil呼び出しは重い）
        self._mem_counter += dt
        if self._mem_counter >= 1.0:
            self._mem_mb = self._process.memory_info().rss / 1024 / 1024
            self._mem_counter = 0

        p = player.entity
        block_name = BLOCK_TYPES[hotbar.selected][0]
        mode = 'GRAVITY' if gravity_on else 'FLY'
        yaw = player.yaw % 360
        pitch = player.pitch
        facing = self._facing_from_yaw(yaw)

        world_name = (
            os.path.basename(world.save_path).replace('.json', '')
            if world.save_path
            else 'Multiplayer'
        )

        self.text.text = (
            f'World: {world_name}\n'
            f'FPS: {self._fps:.0f}\n'
            f'Memory: {self._mem_mb:.0f} MB\n'
            f'XYZ: {p.x:.2f} / {p.y:.2f} / {p.z:.2f}\n'
            f'Block: {int(p.x)} {int(p.y)} {int(p.z)}\n'
            f'Facing: {facing}\n'
            f'Yaw/Pitch: {yaw:.1f} / {pitch:.1f}\n'
            f'Mode: {mode}\n'
            f'Selected: {block_name}\n'
            f'Blocks: {len(world.boxes)}'
        )
    
    @staticmethod
    def _facing_from_yaw(yaw):
        directions = ['South (+Z)', 'West (-X)', 'North (-Z)', 'East (+X)']
        idx = int((yaw + 45) % 360 / 90)
        return directions[idx]