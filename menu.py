import json
import os

from ursina import Button, Entity, Text, camera, color, destroy
from ursina.prefabs.input_field import InputField

from config import SAVE_DIR


VISIBLE_WORLD_COUNT = 5


class WorldSelectMenu:
    def __init__(self, on_select, on_back=None):
        self.on_select = on_select
        self.on_back = on_back
        self.root = Entity(parent=camera.ui)
        self.root.input = self._input
        self.use_template = True

        self.files = sorted(
            (filename for filename in os.listdir(SAVE_DIR)
             if filename.endswith('.json')),
            key=lambda filename: filename.lower(),
        )
        self.scroll_index = 0
        self.world_buttons = []

        Text(
            parent=self.root,
            text='SELECT WORLD',
            origin=(0, 0),
            y=0.42,
            scale=2.5,
            color=color.white,
        )

        self.up_button = Button(
            parent=self.root,
            text='▲',
            position=(0.34, 0.31),
            scale=(0.055, 0.045),
            color=color.dark_gray,
            on_click=lambda: self._scroll(-1),
        )

        y = 0.28
        for _ in range(VISIBLE_WORLD_COUNT):
            button = Button(
                parent=self.root,
                text='',
                y=y,
                scale=(0.6, 0.05),
                color=color.dark_gray,
            )
            self.world_buttons.append(button)
            y -= 0.06

        self.down_button = Button(
            parent=self.root,
            text='▼',
            position=(0.34, 0.01),
            scale=(0.055, 0.045),
            color=color.dark_gray,
            on_click=lambda: self._scroll(1),
        )

        self.empty_text = Text(
            parent=self.root,
            text='(no saved worlds)',
            origin=(0, 0),
            y=0.16,
            scale=1.2,
            color=color.gray,
            enabled=False,
        )

        Text(
            parent=self.root,
            text='New World:',
            origin=(0, 0),
            y=-0.08,
            scale=1.2,
            color=color.white,
        )

        self.input = InputField(parent=self.root, y=-0.14)

        self.template_toggle = Button(
            parent=self.root,
            text='TEMPLATE: ON',
            y=-0.22,
            scale=(0.32, 0.05),
            color=color.azure,
            on_click=self._toggle_template,
        )

        Button(
            parent=self.root,
            text='CREATE',
            y=-0.30,
            scale=(0.25, 0.05),
            color=color.azure,
            on_click=self._create,
        )

        Button(
            parent=self.root,
            text='BACK',
            y=-0.38,
            scale=(0.25, 0.05),
            color=color.dark_gray,
            on_click=self._back,
        )

        self._refresh_world_buttons()

    def _refresh_world_buttons(self):
        max_index = max(0, len(self.files) - VISIBLE_WORLD_COUNT)
        self.scroll_index = max(0, min(self.scroll_index, max_index))

        visible_files = self.files[
            self.scroll_index:self.scroll_index + VISIBLE_WORLD_COUNT
        ]

        for index, button in enumerate(self.world_buttons):
            if index < len(visible_files):
                filename = visible_files[index]
                button.text = self._get_info(filename)
                button.on_click = self._make_load_fn(filename)
                button.enabled = True
            else:
                button.text = ''
                button.on_click = None
                button.enabled = False

        self.empty_text.enabled = not self.files
        self.up_button.enabled = self.scroll_index > 0
        self.down_button.enabled = self.scroll_index < max_index

    def _scroll(self, amount):
        old_index = self.scroll_index
        max_index = max(0, len(self.files) - VISIBLE_WORLD_COUNT)
        self.scroll_index = max(
            0,
            min(self.scroll_index + amount, max_index),
        )
        if self.scroll_index != old_index:
            self._refresh_world_buttons()

    def _input(self, key):
        if key == 'scroll up':
            self._scroll(-1)
        elif key == 'scroll down':
            self._scroll(1)
        elif key in ('up arrow', 'w'):
            self._scroll(-1)
        elif key in ('down arrow', 's'):
            self._scroll(1)

    def _get_info(self, filename):
        path = os.path.join(SAVE_DIR, filename)
        name = filename[:-5]
        try:
            with open(path, encoding='utf-8') as save_file:
                data = json.load(save_file)
            blocks = len(data.get('blocks', []))
            last = data.get('last_played', '?')[:10]
            return f'{name}  [{blocks} blocks / {last}]'
        except (OSError, ValueError, TypeError):
            return name

    def _make_load_fn(self, filename):
        def load_world():
            path = os.path.join(SAVE_DIR, filename)
            self.close()
            self.on_select(path, is_new=False)

        return load_world

    def _toggle_template(self):
        self.use_template = not self.use_template
        self.template_toggle.text = (
            'TEMPLATE: ON' if self.use_template else 'TEMPLATE: OFF'
        )
        self.template_toggle.color = (
            color.azure if self.use_template else color.dark_gray
        )

    def _create(self):
        name = self.input.text.strip()
        if not name:
            safe = self._next_default_world_name()
        else:
            safe = ''.join(
                character
                for character in name
                if character.isalnum() or character in '_-'
            )
            if not safe:
                return

        path = os.path.join(SAVE_DIR, f'{safe}.json')
        if os.path.exists(path):
            return

        self.close()
        self.on_select(
            path,
            is_new=True,
            use_template=self.use_template,
        )

    @staticmethod
    def _next_default_world_name():
        base_name = '新規ワールド'
        if not os.path.exists(os.path.join(SAVE_DIR, f'{base_name}.json')):
            return base_name

        number = 1
        while True:
            name = f'{base_name}（{number}）'
            path = os.path.join(SAVE_DIR, f'{name}.json')
            if not os.path.exists(path):
                return name
            number += 1

    def close(self):
        if self.root:
            destroy(self.root)
            self.root = None

    def _back(self):
        self.close()
        if self.on_back:
            self.on_back()
