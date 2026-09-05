import os
if os.environ.get('MINECRAFTBUILD_AUDIO') == '0':
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import pygame
from config import SOUND_DIR

from settings import settings


class SoundManager:
    def __init__(self):
        self.enabled = os.environ.get('MINECRAFTBUILD_AUDIO', '1') == '1'
        self.place = None
        self.break_ = None
        self.bgm_path = os.path.join(SOUND_DIR, 'bgm.mp3')

        if not self.enabled:
            return

        try:
            pygame.mixer.init()
        except (pygame.error, OSError) as exc:
            print(f'audio disabled: {exc}')
            return

        self.enabled = True

        se_vol = settings.get('se_volume')
        self.place = self._load(os.path.join(SOUND_DIR, 'place.wav'), volume=se_vol)
        self.break_ = self._load(os.path.join(SOUND_DIR, 'break.wav'), volume=se_vol)


    def _load(self, path, volume=1.0):
        if not self.enabled:
            return None
        if not os.path.exists(path):
            print(f'sound not found: {path}')
            return None
        s = pygame.mixer.Sound(path)
        s.set_volume(volume)
        return s

    def play_place(self):
        if self.place:
            self.place.play()

    def play_break(self):
        if self.break_:
            self.break_.play()

    def start_bgm(self):
        if self.enabled and self.bgm_path and os.path.exists(self.bgm_path):
            pygame.mixer.music.load(self.bgm_path)
            pygame.mixer.music.set_volume(settings.get('bgm_volume'))
            pygame.mixer.music.play(-1)


    def stop_bgm(self):
        if self.enabled:
            pygame.mixer.music.stop()

    def reload_volumes(self):
        """設定変更後に音量を反映"""
        if not self.enabled:
            return
        se_vol = settings.get('se_volume')
        if self.place:
            self.place.set_volume(se_vol)
        if self.break_:
            self.break_.set_volume(se_vol)
        pygame.mixer.music.set_volume(settings.get('bgm_volume'))
