
import os
import sys

APP_NAME = 'MinecraftBuild'
DATA_DIR_NAME = f'{APP_NAME}_Data'


def _resource_dir():
	if getattr(sys, 'frozen', False):
		executable_path = os.path.abspath(sys.executable)
		parts = executable_path.split(os.sep)
		for index, part in enumerate(parts):
			if part.endswith('.app'):
				resources_dir = os.path.join(os.sep.join(parts[:index + 1]), 'Contents', 'Resources')
				if os.path.exists(os.path.join(resources_dir, 'textures')):
					return resources_dir
	if getattr(sys, 'frozen', False):
		return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
	return os.path.dirname(os.path.abspath(__file__))


def _app_relative_data_dir():
	if not getattr(sys, 'frozen', False):
		return BASE_DIR

	executable_path = os.path.abspath(sys.executable)
	parts = executable_path.split(os.sep)
	for index, part in enumerate(parts):
		if part.endswith('.app'):
			app_bundle = os.sep.join(parts[:index + 1])
			return os.path.join(os.path.dirname(app_bundle), DATA_DIR_NAME)
	return os.path.join(os.path.dirname(executable_path), DATA_DIR_NAME)


def resource_path(*parts):
	return os.path.join(RESOURCE_DIR, *parts)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = _resource_dir()
DATA_DIR = _app_relative_data_dir()
SAVE_DIR = os.path.join(DATA_DIR, 'saves')
TEMPLATE_PATH = resource_path('Template.json')
SOUND_DIR = resource_path('sounds')
SETTINGS_PATH = os.path.join(DATA_DIR, 'settings.json')
SCREENSHOTS_DIR = os.path.join(DATA_DIR, 'screenshots')
CRASH_LOG_PATH = os.path.join(DATA_DIR, 'crash.log')
RESOURCE_LOG_PATH = os.path.join(DATA_DIR, 'resources.log')


def ensure_data_dirs():
	os.makedirs(SAVE_DIR, exist_ok=True)
	os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def write_resource_log():
	ensure_data_dirs()
	with open(RESOURCE_LOG_PATH, 'w') as log_file:
		log_file.write(f'RESOURCE_DIR={RESOURCE_DIR}\n')
		log_file.write(f'DATA_DIR={DATA_DIR}\n')
		for name in ('dirt.png', 'grass_atlas.png', 'stone.png'):
			path = resource_path('textures', name)
			log_file.write(f'{path}: {os.path.exists(path)}\n')


ensure_data_dirs()

WORLD_SIZE = 60
RENDER_DISTANCE = 20

PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.3
STANDING_REACH = 0.4

MOVE_SPEED = 4
SNEAK_MUL = 0.3
SPRINT_MUL = 1.6
FRICTION = 12

GRAVITY = 25
JUMP_POWER = 9

REACH = 5
SENSITIVITY = 0.2

DOUBLE_TAP = 0.3
CLICK_INTERVAL = 0.25
SCROLL_INTERVAL = 0.15

SAVE_VERSION = 1