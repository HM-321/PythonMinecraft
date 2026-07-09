import json
import os
from config import SETTINGS_PATH


DEFAULT_SETTINGS = {
    'sensitivity': 0.2,
    'fov': 90,
    'render_distance': 20,
    'bgm_volume': 0.3,
    'se_volume': 0.5,
    'max_fps': 30,
    'key_jump': 'space',
    'key_sneak': 'left shift',
    'key_sprint': 'left control',
    'key_debug': ':',
    'key_screenshot': 'p',
    'key_open_screenshots': ';',
}


class Settings:
    def __init__(self):
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value

    def load(self):
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH) as f:
                    loaded = json.load(f)
                for k, v in loaded.items():
                    if k in DEFAULT_SETTINGS:
                        self.data[k] = v
            except Exception as e:
                print(f'settings load error: {e}')

    def save(self):
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f'settings saved: {SETTINGS_PATH}')


settings = Settings()