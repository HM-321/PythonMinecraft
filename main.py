import os
import time as _pytime
from ursina import *
from panda3d.core import WindowProperties

from settings import settings
from config import SAVE_DIR, WORLD_SIZE, REACH
from config import CLICK_INTERVAL, SCROLL_INTERVAL
from block_types import BLOCK_TYPES
from ui import Crosshair, Hotbar, SelectionFrame, DebugOverlay
from world import World
from player_controller import PlayerController
from menu import WorldSelectMenu
from sound_manager import SoundManager
from controller import Controller

os.makedirs(SAVE_DIR, exist_ok=True)


app = Ursina()
window.color = color.azure

FONT_PATH = '/Users/s13010282/Library/Fonts/JF-Dot-AyuMin18.ttf'
Text.default_font = FONT_PATH
from screeninfo import get_monitors
m = get_monitors()[0]

window.borderless = True
window.size = (m.width, m.height)
window.position = (0, 0)

sound_mgr = SoundManager()
sound_mgr.start_bgm()
controller = Controller()

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
}


def start_game(save_path, is_new):
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
        game['world'].generate_flat()
    else:
        game['world'].load(game['player'].entity)

    def force_redraw():
        p = app.win.getProperties()
        
        print(
            "actual:",
            p.getXSize(),
            p.getYSize()
        )

        w, h = p.getXSize(), p.getYSize()
        np = WindowProperties()
        np.setSize(w + 1, h + 1)
        app.win.requestProperties(np)
        invoke(_restore, w=w, h=h, delay=0.03)

    def _restore(w, h):
        np = WindowProperties()
        np.setSize(w, h)
        app.win.requestProperties(np)

    invoke(force_redraw, delay=0.5)
    game['started'] = True
    



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
    game['world'].save(game['player'].entity)
    sound_mgr.stop_bgm()
    application.quit()


def _reload_app():
    import sys
    if game['started'] and game['world']:
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

    game['world'].place_block(new_pos.x, new_pos.y, new_pos.z,
                              hotbar.selected, orientation=orientation)
    sound_mgr.play_place()


def _try_break_block():
    player = game['player']
    hit = raycast(camera.world_position, camera.forward,
                  distance=REACH, ignore=[player.entity])
    if hit.hit and hit.entity in game['world'].boxes:
        game['world'].remove_block(hit.entity)
        sound_mgr.play_break()


def _take_screenshot():
    from datetime import datetime
    ss_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
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
    title = TitleScreen(on_start=_show_menu)


def _show_menu():
    global menu
    menu = WorldSelectMenu(on_select=start_game)


title = None
menu = None

invoke(_show_title, delay=0.3)


def _center():
    w = app.win.getProperties().getXSize()
    h = app.win.getProperties().getYSize()
    return w // 2, h // 2



def update():
    if not game['started']:
        _limit_fps()
        return

    game['esc_cd'] = max(0, game['esc_cd'] - time.dt)

    if game['paused']:
        _limit_fps()
        return

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

    controller.update()
    if controller.is_connected():
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

        if controller.zl_just_pressed():
            if game['click_cd'] <= 0:
                game['click_cd'] = CLICK_INTERVAL
                _try_place_block()

        if controller.zr_just_pressed():
            if game['click_cd'] <= 0:
                game['click_cd'] = CLICK_INTERVAL
                _try_break_block()

    # ===== 通常のtick処理 =====
    player.tick(time.dt)
    game['click_cd'] = max(0, game['click_cd'] - time.dt)
    game['scroll_cd'] = max(0, game['scroll_cd'] - time.dt)

    player.update_movement()

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
        ss_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
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

    player = game['player']
    hit = raycast(camera.world_position, camera.forward,
                  distance=REACH, ignore=[player.entity])
    if not hit.hit or hit.entity not in game['world'].boxes:
        return

    target = hit.entity

    if key == 'left mouse down':
        game['world'].remove_block(target)
        sound_mgr.play_break()

    if key == 'right mouse down':
        hit_point = hit.world_point
        target_pos = target.position
        if getattr(target, 'custom_mesh', False):
            target_pos = Vec3(target_pos.x, target_pos.y + 0.5, target_pos.z)
        center = Vec3(target_pos.x, target_pos.y - 0.5, target_pos.z)

        diff = hit_point - center
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

        game['world'].place_block(new_pos.x, new_pos.y, new_pos.z,
                                  hotbar.selected, orientation=orientation)
        sound_mgr.play_place()


app.run()