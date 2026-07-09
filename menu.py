import json
import os
from ursina import Entity, Text, Button, camera, color, destroy
from ursina.prefabs.input_field import InputField
from config import SAVE_DIR


class WorldSelectMenu:
    def __init__(self, on_select):
        self.on_select = on_select
        self.root = Entity(parent=camera.ui)

        Text(parent=self.root, text='SELECT WORLD',
             origin=(0, 0), y=0.4, scale=2.5, color=color.white)

        files = sorted([f for f in os.listdir(SAVE_DIR)
                        if f.endswith('.json')])

        y = 0.28
        if not files:
            Text(parent=self.root, text='(no saved worlds)',
                 origin=(0, 0), y=y, scale=1.2, color=color.gray)
            y -= 0.06

        for f in files[:8]:
            info = self._get_info(f)
            Button(
                parent=self.root, text=info,
                y=y, scale=(0.6, 0.05),
                color=color.dark_gray,
                on_click=self._make_load_fn(f),
            )
            y -= 0.06

        y -= 0.05
        Text(parent=self.root, text='New World:',
             origin=(0, 0), y=y, scale=1.2, color=color.white)
        y -= 0.06

        self.input = InputField(parent=self.root, y=y)
        y -= 0.08

        Button(
            parent=self.root, text='CREATE',
            y=y, scale=(0.25, 0.05),
            color=color.azure,
            on_click=self._create,
        )

    def _get_info(self, filename):
        path = os.path.join(SAVE_DIR, filename)
        name = filename[:-5]
        try:
            with open(path) as f:
                data = json.load(f)
            blocks = len(data.get('blocks', []))
            last = data.get('last_played', '?')[:10]
            return f'{name}  [{blocks} blocks / {last}]'
        except Exception:
            return name

    def _make_load_fn(self, filename):
        def fn():
            path = os.path.join(SAVE_DIR, filename)
            self.close()
            self.on_select(path, is_new=False)
        return fn

    def _create(self):
        name = self.input.text.strip()
        if not name:
            return
        safe = ''.join(c for c in name if c.isalnum() or c in '_-')
        if not safe:
            return
        path = os.path.join(SAVE_DIR, f'{safe}.json')
        if os.path.exists(path):
            return
        self.close()
        self.on_select(path, is_new=True)

    def close(self):
        destroy(self.root)