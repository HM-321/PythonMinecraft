import json
import os
from config import SETTINGS_PATH

DEFAULT_SETTINGS = {
    'sensitivity': 0.2,
    'controller_sensitivity': 300,
    'fov': 90,
    'render_distance': 20,
    'bgm_volume': 0.3,
    'se_volume': 0.5,
    'max_fps': 30,
    'last_server_host': '192.168.0.1',
    'last_server_port': 25565,
    'key_jump': 'space',
    'key_sneak': 'left shift',
    'key_sprint': 'left control',
    'key_debug': ':',
    'key_screenshot': 'p',
    'key_open_screenshots': ';',
    # コントローラー
    'ctrl_jump': 'A',
    'ctrl_sneak': 'B',
    'ctrl_pause': 'Y',        # Menuボタンないので Y に
    'ctrl_dash': 'X',         # LS押込取れないので X に
    'ctrl_fly_toggle': 'dpad_up',
    'ctrl_hotbar_prev': 'LB',
    'ctrl_hotbar_next': 'RB',
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
        else:
            self.save()

    def save(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f'settings saved: {SETTINGS_PATH}')


settings = Settings()