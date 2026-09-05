import os
import sys
import shutil
import time as _pytime
from pathlib import Path

from ursina import *
from ursina import application
from panda3d.core import WindowProperties

from app_runtime import install_crash_logging
from settings import settings
from config import (
    RESOURCE_DIR,
    SAVE_DIR,
    TEMPLATE_PATH,
    SCREENSHOTS_DIR,
    WORLD_SIZE,
    REACH,
    write_resource_log,
)
from config import CLICK_INTERVAL, SCROLL_INTERVAL
from block_types import BLOCK_TYPES
from ui import Crosshair, Hotbar, SelectionFrame, DebugOverlay
from world import World
from player_controller import PlayerController
from menu import WorldSelectMenu
from sound_manager import SoundManager
from controller import Controller
from block_particles import BlockParticles
from multiplayer_client import MultiplayerClient
from player_model import RemotePlayer


install_crash_logging()
os.makedirs(SAVE_DIR, exist_ok=True)
os.chdir(RESOURCE_DIR)
application.asset_folder = Path(RESOURCE_DIR)
write_resource_log()


app = Ursina()
application.asset_folder = Path(RESOURCE_DIR)
window.color = color.azure


from panda3d.core import WindowProperties, getModelPath


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        if sys.platform == 'darwin':
            base_path = Path(sys.executable).resolve().parent.parent / 'Resources'
        else:
            base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    return Path(base_path) / relative_path


# ===== 内蔵フォント =====
FONT_PATH = resource_path('fonts/JF-Dot-AyuMin18.ttf')
FONT_DIR = FONT_PATH.parent

print('FONT_PATH =', FONT_PATH)
print('FONT_EXISTS =', FONT_PATH.is_file())
print('FONT_DIR =', FONT_DIR)

if not FONT_PATH.is_file():
    raise FileNotFoundError(f'Font not found: {FONT_PATH}')

# Ursina側
application.fonts_folder = FONT_DIR

# Panda3D側
model_path = getModelPath()
model_path.append_path(str(FONT_DIR.resolve()))

# フォント名を指定
Text.default_font = FONT_PATH.name

print('Text.default_font =', Text.default_font)

from screeninfo import get_monitors
m = get_monitors()[0]

window.borderless = True
window.size = (m.width, m.height)
window.position = (0, 0)

sound_mgr = SoundManager()
sound_mgr.start_bgm()
controller = Controller()
block_particles = BlockParticles()

import options
options.sound_mgr = sound_mgr


# ===== FPS制限 =====
_last_frame = _pytime.time()

def _limit_fps():
    global _last_frame
    now = _pytime.time()
    target_fps = settings.get('max_fps')
    target_dt = 1.0 / target_fps
    elapsed = now - _last_frame
    if elapsed < target_dt:
        _pytime.sleep(target_dt - elapsed)
    _last_frame = _pytime.time()


game = {
    'started': False,
    'paused': False,
    'pause_menu': None,
    'world': None,
    'player': None,
    'hotbar': None,
    'crosshair': None,      # ← 追加
    'selection': None,
    'debug': None,
    'first_frame': True,
    'click_cd': 0,
    'scroll_cd': 0,
    'esc_cd': 0,
    'cull_counter': 0,
    'network_client': None,
    'network_pending': None,
    'network_player_id': None,
    'remote_players': {},
    'network_state_cd': 0,
    'window_focused': True,
}


def start_game(save_path, is_new, use_template=False):
    sound_mgr.stop_bgm()
    props = WindowProperties()
    props.setCursorHidden(True)
    app.win.requestProperties(props)
    mouse.visible = False

    game['crosshair'] = Crosshair()
    game['hotbar'] = Hotbar()
    game['hotbar']._refresh()
    game['selection'] = SelectionFrame()
    game['debug'] = DebugOverlay()

    game['player'] = PlayerController((WORLD_SIZE / 2, 3, WORLD_SIZE / 2))
    camera.fov = settings.get('fov')
    game['world'] = World(save_path)

    if is_new:
        if use_template:
            if os.path.exists(TEMPLATE_PATH):
                shutil.copyfile(TEMPLATE_PATH, save_path)
                game['world'].load(game['player'].entity)
            else:
                game['world'].generate_flat()
        else:
            game['world'].generate_flat()
        game['player'].yaw = 0
        game['player'].pitch = -17.5
        game['player'].entity.rotation_y = 0
        camera.rotation_x = -17.5
    else:
        game['world'].load(game['player'].entity)

    game['started'] = True


def _start_network_game(snapshot):
    client = game['network_client']
    player_id = snapshot['player_id']
    own_player = next((p for p in snapshot.get('players', [])
                       if p.get('id') == player_id), None)
    spawn = (WORLD_SIZE / 2, 3, WORLD_SIZE / 2)
    if own_player:
        spawn = (own_player.get('x', spawn[0]), own_player.get('y', spawn[1]),
                 own_player.get('z', spawn[2]))

    sound_mgr.stop_bgm()
    props = WindowProperties()
    props.setCursorHidden(True)
    app.win.requestProperties(props)
    mouse.visible = False

    game['crosshair'] = Crosshair()
    game['hotbar'] = Hotbar()
    game['hotbar']._refresh()
    game['selection'] = SelectionFrame()
    game['debug'] = DebugOverlay()
    game['player'] = PlayerController(spawn)
    if own_player:
        game['player'].yaw = own_player.get('yaw', 0)
        game['player'].pitch = own_player.get('pitch', 0)
        game['player'].gravity_on = own_player.get('gravity_on', True)
        game['player'].entity.rotation_y = game['player'].yaw
        camera.rotation_x = game['player'].pitch
    camera.fov = settings.get('fov')
    game['world'] = World(None)
    for block in snapshot.get('blocks', []):
        if len(block) >= 4:
            game['world'].place_block(*block[:3], block[3],
                                      orientation=block[4] if len(block) > 4 else 'y')

    game['remote_players'] = {}
    game['network_player_id'] = player_id
    for remote in snapshot.get('players', []):
        if remote.get('id') != player_id:
            _update_remote_player(remote)
    game['network_pending'] = None
    game['network_state_cd'] = 0
    game['started'] = True


def _update_remote_player(data):
    player_id = data.get('id')
    if player_id is None or player_id == game.get('network_player_id'):
        return
    remote = game['remote_players'].get(player_id)
    if remote is None:
        remote = RemotePlayer(player_id)
        game['remote_players'][player_id] = remote
    remote.update(
        (data.get('x', 0), data.get('y', 0), data.get('z', 0)),
        yaw=data.get('yaw', 0),
        pitch=data.get('pitch', 0),
        moving=data.get('moving', False),
        sneaking=data.get('sneaking', False),
        dt=time.dt,
    )


def _process_network_events():
    client = game.get('network_client')
    if not client:
        return
    for message in client.poll():
        message_type = message.get('type')
        if message_type == 'world_snapshot' and not game['started']:
            _start_network_game(message)
        elif message_type == 'world_reset' and game.get('network_client'):
            _reset_network_world(message.get('blocks', []))
        elif message_type == 'player_join':
            _update_remote_player(message.get('player', {}))
        elif message_type == 'player_state':
            _update_remote_player(message.get('player', {}))
        elif message_type == 'player_leave':
            remote = game['remote_players'].pop(message.get('id'), None)
            if remote:
                remote.destroy()
        elif message_type == 'block_changed':
            _apply_network_block_change(message)
        elif message_type in ('error', 'disconnected'):
            print(f'multiplayer: {message.get("message", message.get("reason", "error"))}')
            if message_type == 'disconnected':
                _handle_network_disconnect()
                return


def _handle_network_disconnect():
    if game.get('started'):
        _save_and_quit()
        return
    client = game.get('network_client')
    if client:
        client.close()
    game['network_client'] = None
    game['network_pending'] = None
    _show_title()


def _apply_network_block_change(message):
    world = game.get('world')
    if not world:
        return
    position = (message.get('x'), message.get('y'), message.get('z'))
    if None in position:
        return
    if message.get('action') == 'break' and game.get('network_client'):
        game['network_client'].acknowledge_break(*position)
    def block_position(block):
        return getattr(block, 'block_position',
                       (round(block.x), round(block.y), round(block.z)))

    existing = next((block for block in world.boxes
                     if block_position(block) == position), None)
    if message.get('action') == 'break':
        if existing:
            block_particles.burst(existing)
            world.remove_block(existing)
            sound_mgr.play_break()
    elif message.get('action') == 'move':
        old_position = (message.get('from_x'), message.get('from_y'),
                        message.get('from_z'))
        if None not in old_position:
            world.move_block(old_position, position,
                             message.get('block_id', 5),
                             message.get('orientation', 'y'))
    elif message.get('action') == 'place' and not existing:
        world.place_block(*position, message.get('block_id', 0),
                          orientation=message.get('orientation', 'y'))
        sound_mgr.play_place()


def _reset_network_world(blocks):
    world = game.get('world')
    if not world:
        return
    world.clear()
    for block in blocks:
        if len(block) >= 4:
            world.place_block(*block[:3], block[3],
                              orientation=block[4] if len(block) > 4 else 'y')
    



def _open_pause_menu():
    from pause_menu import PauseMenu
    game['paused'] = True
    game['pause_menu'] = PauseMenu(
        on_resume=_resume_game,
        on_quit=_save_and_quit,
        app=app,
    )


def _resume_game():
    game['paused'] = False
    game['pause_menu'] = None
    game['first_frame'] = True


def _save_and_quit():
    network_client = game.get('network_client')
    was_network_game = network_client is not None
    if network_client:
        network_client.close()
    elif game.get('world') and game.get('player'):
        game['world'].save(game['player'].entity)
    sound_mgr.stop_bgm()

    if game.get('pause_menu'):
        game['pause_menu'] = None
    for key in ('crosshair', 'hotbar', 'selection', 'debug'):
        obj = game.get(key)
        if obj:
            destroy(getattr(obj, 'root', obj))

    if game.get('world'):
        for block in game['world'].boxes:
            destroy(block)
    for remote in game.get('remote_players', {}).values():
        remote.destroy()
    if game.get('player'):
        destroy(game['player'].entity)

    props = WindowProperties()
    props.setCursorHidden(False)
    app.win.requestProperties(props)
    mouse.visible = True
    mouse.locked = False
    camera.parent = scene
    camera.position = (0, 0, 0)
    camera.rotation = (0, 0, 0)

    game.update({
        'started': False,
        'paused': False,
        'world': None,
        'player': None,
        'pause_menu': None,
        'crosshair': None,
        'hotbar': None,
        'selection': None,
        'debug': None,
        'first_frame': True,
        'network_client': None,
        'network_pending': None,
        'network_player_id': None,
        'remote_players': {},
    })
    sound_mgr.start_bgm()
    if was_network_game:
        _show_title()
    else:
        _show_menu()


def _reload_app():
    import sys
    if game['started'] and game['world'] and not game.get('network_client'):
        try:
            game['world'].save(game['player'].entity)
        except Exception:
            pass
    if sound_mgr:
        sound_mgr.stop_bgm()
    os.execv(sys.executable, [sys.executable] + sys.argv)
    
def _try_place_block():
    player = game['player']
    hotbar = game['hotbar']
    hit = raycast(camera.world_position, camera.forward,
                  distance=REACH, ignore=[player.entity])
    if not hit.hit or hit.entity not in game['world'].boxes:
        return

    target = hit.entity
    hit_point = hit.world_point
    target_pos = target.position
    if getattr(target, 'custom_mesh', False):
        target_pos = Vec3(target_pos.x, target_pos.y + 0.5, target_pos.z)
    center_pos = Vec3(target_pos.x, target_pos.y - 0.5, target_pos.z)

    diff = hit_point - center_pos
    ax, ay, az = abs(diff.x), abs(diff.y), abs(diff.z)

    if ax >= ay and ax >= az:
        normal = Vec3(1 if diff.x > 0 else -1, 0, 0)
    elif ay >= ax and ay >= az:
        normal = Vec3(0, 1 if diff.y > 0 else -1, 0)
    else:
        normal = Vec3(0, 0, 1 if diff.z > 0 else -1)

    new_pos = target_pos + normal

    if player.block_overlaps(new_pos):
        return
    if player.is_above_standing_block(new_pos):
        return

    _, _, tex_info = BLOCK_TYPES[hotbar.selected]
    is_rotatable = isinstance(tex_info, dict) and tex_info.get('rotatable', False)

    if is_rotatable:
        if abs(normal.y) > 0.5:
            orientation = 'y'
        elif abs(normal.x) > 0.5:
            orientation = 'x'
        else:
            orientation = 'z'
    else:
        orientation = 'y'

    if game.get('network_client'):
        game['network_client'].request_place(
            new_pos.x, new_pos.y, new_pos.z, hotbar.selected, orientation,
            player_state={
                'x': player.entity.x,
                'y': player.entity.y,
                'z': player.entity.z,
            })
        return

    game['world'].place_block(new_pos.x, new_pos.y, new_pos.z,
                              hotbar.selected, orientation=orientation)
    sound_mgr.play_place()


def _try_break_block():
    player = game['player']
    hit = raycast(camera.world_position, camera.forward,
                  distance=REACH, ignore=[player.entity])
    if hit.hit and hit.entity in game['world'].boxes:
        if game.get('network_client'):
            target_position = getattr(
                hit.entity, 'block_position',
                (round(hit.entity.x), round(hit.entity.y), round(hit.entity.z)))
            game['network_client'].request_break(
                *target_position)
            return
        block_particles.burst(hit.entity)
        game['world'].remove_block(hit.entity)
        sound_mgr.play_break()


def _take_screenshot():
    from datetime import datetime
    ss_dir = SCREENSHOTS_DIR
    os.makedirs(ss_dir, exist_ok=True)
    filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '.png'
    path = os.path.join(ss_dir, filename)

    hide_targets = []
    if game.get('selection'):
        hide_targets.append(game['selection'].root)
    if game.get('hotbar'):
        hide_targets.append(game['hotbar'].root)

    for e in hide_targets:
        e.enabled = False

    def _do():
        app.win.saveScreenshot(path)
        print(f'screenshot: {path}')
        for e in hide_targets:
            e.enabled = True

    invoke(_do, delay=0.05)


from title import TitleScreen


def _show_title():
    global title
    title = TitleScreen(on_start=_show_menu, on_multiplayer=_show_multiplayer_menu)


def _show_menu():
    global menu
    menu = WorldSelectMenu(on_select=start_game, on_back=_show_title)


def _show_multiplayer_menu():
    from multiplayer_menu import MultiplayerMenu
    global multiplayer_menu
    multiplayer_menu = MultiplayerMenu(
        on_join=_join_multiplayer,
        on_back=_show_title,
    )


def _join_multiplayer(host, port, join_menu):
    client = MultiplayerClient(host, port)
    try:
        client.connect()
    except (OSError, ValueError) as exc:
        if isinstance(exc, OSError) and getattr(exc, 'errno', None) == 61:
            message = 'CONNECTION REFUSED: CHECK SERVER IP, PORT, AND FIREWALL'
        else:
            message = f'CONNECTION FAILED: {exc}'
        join_menu.show_error(message)
        return
    join_menu.close()
    game['network_client'] = client
    game['network_pending'] = client


title = None
menu = None

invoke(_show_title, delay=0.3)


def _center():
    w = app.win.getProperties().getXSize()
    h = app.win.getProperties().getYSize()
    return w // 2, h // 2


def _update_window_focus():
    focused = app.win.getProperties().getForeground()
    if focused == game['window_focused']:
        return

    game['window_focused'] = focused
    if not focused and game['started'] and not game['paused']:
        _open_pause_menu()



def update():
    block_particles.update()
    _process_network_events()

    if not game['started']:
        _limit_fps()
        return

    _update_window_focus()
    controller.update()
    game['esc_cd'] = max(0, game['esc_cd'] - time.dt)

    if game['paused']:
        _limit_fps()
        return

    game['world'].update_sand(time.dt)

    cx, cy = _center()
    if game['first_frame']:
        app.win.movePointer(0, cx, cy)
        game['first_frame'] = False
        _limit_fps()
        return

    # ===== マウス視点 =====
    md = app.win.getPointer(0)
    dx = md.getX() - cx
    dy = md.getY() - cy

    player = game['player']
    player.update_view(dx, dy)
    app.win.movePointer(0, cx, cy)

    if controller.is_connected():
        if controller.button_pressed(settings.get('ctrl_jump')):
            player.try_toggle_gravity()
        look_x = controller.look_x()
        look_y = controller.look_y()
        if look_x != 0 or look_y != 0:
            sens = settings.get('controller_sensitivity')
            player.yaw += look_x * sens * time.dt
            player.pitch += look_y * sens * time.dt
            player.pitch = max(-90, min(90, player.pitch))
            player.entity.rotation_y = player.yaw
            camera.rotation_x = player.pitch

        hotbar = game['hotbar']

        if controller.button_pressed(settings.get('ctrl_hotbar_prev')):
            hotbar.cycle(-1)
        if controller.button_pressed(settings.get('ctrl_hotbar_next')):
            hotbar.cycle(1)

        if controller.button_pressed(settings.get('ctrl_fly_toggle')):
            player.gravity_on = not player.gravity_on
            player.velocity_y = 0

        if controller.button_pressed(settings.get('ctrl_pause')):
            _open_pause_menu()
            _limit_fps()
            return

        if controller.zl_held():
            if game['click_cd'] <= 0:
                game['click_cd'] = CLICK_INTERVAL
                _try_place_block()

        if controller.zr_held():
            if game['click_cd'] <= 0:
                game['click_cd'] = CLICK_INTERVAL
                _try_break_block()

    if held_keys['left mouse'] and game['click_cd'] <= 0:
        game['click_cd'] = CLICK_INTERVAL
        _try_break_block()
    elif held_keys['right mouse'] and game['click_cd'] <= 0:
        game['click_cd'] = CLICK_INTERVAL
        _try_place_block()

    # ===== 通常のtick処理 =====
    player.tick(time.dt)
    game['click_cd'] = max(0, game['click_cd'] - time.dt)
    game['scroll_cd'] = max(0, game['scroll_cd'] - time.dt)

    player.update_movement()

    if game.get('network_client'):
        game['network_state_cd'] -= time.dt
        if game['network_state_cd'] <= 0:
            game['network_state_cd'] = 0.05
            try:
                game['network_client'].send_player_state({
                    'x': player.entity.x,
                    'y': player.entity.y,
                    'z': player.entity.z,
                    'yaw': player.yaw,
                    'pitch': player.pitch,
                    'gravity_on': player.gravity_on,
                    'moving': player.velocity_h.length() > 0.1,
                    'sneaking': player.sneaking,
                })
            except (OSError, RuntimeError):
                _handle_network_disconnect()
                return

    # ===== 選択枠 =====
    hit = raycast(camera.world_position, camera.forward,
                  distance=REACH, ignore=[player.entity])
    if hit.hit and hit.entity in game['world'].boxes:
        game['selection'].show_at(hit.entity)
    else:
        game['selection'].hide()

    # ===== 距離カリング =====
    game['cull_counter'] = (game['cull_counter'] + 1) % 5
    if game['cull_counter'] == 0:
        px, pz = player.entity.x, player.entity.z
        rd = settings.get('render_distance')
        rd2 = rd * rd
        for b in game['world'].boxes:
            b.enabled = ((b.x - px) ** 2 + (b.z - pz) ** 2) < rd2

    game['hotbar'].maybe_hide()
    game['debug'].update(
        time.dt,
        game['player'],
        game['hotbar'],
        game['world'],
        game['player'].gravity_on,
    )

    _limit_fps()
    

def input(key):
    if not game['started']:
        return

    if key == 'escape':
        if game['esc_cd'] > 0:
            return
        game['esc_cd'] = 0.3
        if game['paused']:
            if game['pause_menu']:
                game['pause_menu']._resume()
            return
        _open_pause_menu()
        return

    if game['paused']:
        return

    # Ctrl + Alt + F5 で再起動
    if key == 'f5':
        if held_keys['left control'] and held_keys['left alt']:
            _reload_app()
            return

    key_debug = settings.get('key_debug')
    key_screenshot = settings.get('key_screenshot')
    key_open_ss = settings.get('key_open_screenshots')
    key_jump = settings.get('key_jump')

    if key == key_debug:
        game['debug'].toggle()
        return

    if key == key_screenshot:
        _take_screenshot()
        return

    if key == key_open_ss:
        ss_dir = SCREENSHOTS_DIR
        import subprocess
        subprocess.Popen(['open', ss_dir])
        return

    hotbar = game['hotbar']

    if key.isdigit():
        idx = int(key) - 1
        if 0 <= idx < len(BLOCK_TYPES):
            hotbar.set_selected(idx)
            return

    if key in ('scroll up', 'scroll down'):
        if game['scroll_cd'] > 0:
            return
        game['scroll_cd'] = SCROLL_INTERVAL
        hotbar.cycle(-1 if key == 'scroll up' else 1)
        return

    if key == key_jump:
        game['player'].try_toggle_gravity()

    if key not in ('left mouse down', 'right mouse down'):
        return

    if game['click_cd'] > 0:
        return
    game['click_cd'] = CLICK_INTERVAL

    if key == 'left mouse down':
        _try_break_block()
        return
    if key == 'right mouse down':
        _try_place_block()
        return


app.run()