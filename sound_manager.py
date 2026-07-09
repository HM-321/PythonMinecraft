import os
import pygame
from config import BASE_DIR

from settings import settings


class SoundManager:
    def __init__(self):
        pygame.mixer.init()

        sound_dir = os.path.join(BASE_DIR, 'sounds')
        se_vol = settings.get('se_volume')
        self.place = self._load(os.path.join(sound_dir, 'place.wav'), volume=se_vol)
        self.break_ = self._load(os.path.join(sound_dir, 'break.wav'), volume=se_vol)
        self.bgm_path = os.path.join(sound_dir, 'bgm.mp3')


    def _load(self, path, volume=1.0):
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
        if self.bgm_path and os.path.exists(self.bgm_path):
            pygame.mixer.music.load(self.bgm_path)
            pygame.mixer.music.set_volume(settings.get('bgm_volume'))
            pygame.mixer.music.play(-1)


    def stop_bgm(self):
        pygame.mixer.music.stop()

    def reload_volumes(self):
        """設定変更後に音量を反映"""
        se_vol = settings.get('se_volume')
        if self.place:
            self.place.set_volume(se_vol)
        if self.break_:
            self.break_.set_volume(se_vol)
        pygame.mixer.music.set_volume(settings.get('bgm_volume'))
