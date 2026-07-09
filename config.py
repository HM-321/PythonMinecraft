
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, 'saves')
SOUND_DIR = os.path.join(BASE_DIR, 'sounds')
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'screenshots')

WORLD_SIZE = 60
RENDER_DISTANCE = 20

PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.3
STANDING_REACH = 0.4

MOVE_SPEED = 6
SNEAK_MUL = 0.3
SPRINT_MUL = 1.6
FRICTION = 12

GRAVITY = 25
JUMP_POWER = 9

REACH = 5
SENSITIVITY = 0.2

DOUBLE_TAP = 0.3
CLICK_INTERVAL = 0.15
SCROLL_INTERVAL = 0.15

SAVE_VERSION = 1

SOUND_DIR = os.path.join(BASE_DIR, 'sounds')