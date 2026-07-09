from ursina import *
from panda3d.core import WindowProperties
import json
import os

# ===== セーブディレクトリ =====
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saves')
os.makedirs(SAVE_DIR, exist_ok=True)


# ===== 起動時: ワールド選択 or 新規作成 =====
def choose_world():
    files = sorted([f for f in os.listdir(SAVE_DIR) if f.endswith('.json')])
    print('\n' + '=' * 40)
    print('  WORLDS')
    print('=' * 40)
    if files:
        for i, f in enumerate(files, 1):
            path = os.path.join(SAVE_DIR, f)
            size = os.path.getsize(path) // 1024
            print(f'  {i}: {f[:-5]} ({size}KB)')
    else:
        print('  (no worlds)')
    print('=' * 40)
    print('  n: create new world')
    print('=' * 40)

    while True:
        s = input('Select: ').strip().lower()
        if s == 'n':
            name = input('New world name: ').strip()
            if not name:
                continue
            # ファイル名に使えない文字を除去
            safe = ''.join(c for c in name if c.isalnum() or c in '_-')
            if not safe:
                print('invalid name')
                continue
            return os.path.join(SAVE_DIR, f'{safe}.json'), True
        if s.isdigit():
            idx = int(s) - 1
            if 0 <= idx < len(files):
                return os.path.join(SAVE_DIR, files[idx]), False
        print('invalid input')


SAVE_PATH, IS_NEW = choose_world()

# ===== Ursina起動 =====
app = Ursina()
window.color = color.azure


def hide_mouse():
    props = WindowProperties()
    props.setCursorHidden(True)
    app.win.requestProperties(props)


hide_mouse()
mouse.visible = False

# ===== クロスヘア =====
aspect = window.aspect_ratio
crosshair = Entity(parent=camera.ui)
Entity(parent=crosshair, model='quad', color=color.white,
       scale=(0.015, 0.003), z=-1)
Entity(parent=crosshair, model='quad', color=color.white,
       scale=(0.003, 0.015), z=-1)

# ===== ブロック種類 =====
BLOCK_TYPES = [
    ('Grass', color.white, 'textures/grass.png'),
    ('Dirt',  color.white, 'textures/dirt.png'),
    ('Stone', color.white, 'textures/stone.png'),
    ('Wood',  color.white, 'textures/wood.png'),
    ('Leaf',  color.white, 'textures/leaf.png'),
    ('Sand',  color.white, 'textures/sand.png'),
    ('Brick', color.white, 'textures/brick.png'),
    ('Glass', color.white, 'textures/glass.png'),
]
selected_block = 0

# ===== ホットバー =====
SLOT = 0.05
GAP = 0.01
BORDER = 0.004
step_x = SLOT + GAP

hotbar = Entity(parent=camera.ui, position=(0, -0.45))

for idx, (name, col, tex) in enumerate(BLOCK_TYPES):
    x = (idx - (len(BLOCK_TYPES) - 1) / 2) * step_x
    Entity(parent=hotbar, model='quad',
           color=color.dark_gray,
           position=(x, 0, 0.01),
           scale=(SLOT, SLOT))
    Entity(parent=hotbar, model='quad',
           color=col, texture=tex,
           position=(x, 0, 0),
           scale=(SLOT * 0.8, SLOT * 0.8))

selector_border = Entity(parent=hotbar)
Entity(parent=selector_border, model='quad', color=color.yellow,
       position=(0, SLOT * 0.55), scale=(SLOT * 1.15, BORDER))
Entity(parent=selector_border, model='quad', color=color.yellow,
       position=(0, -SLOT * 0.55), scale=(SLOT * 1.15, BORDER))
Entity(parent=selector_border, model='quad', color=color.yellow,
       position=(-SLOT * 0.55, 0), scale=(BORDER, SLOT * 1.15))
Entity(parent=selector_border, model='quad', color=color.yellow,
       position=(SLOT * 0.55, 0), scale=(BORDER, SLOT * 1.15))


def update_selector():
    x = (selected_block - (len(BLOCK_TYPES) - 1) / 2) * step_x
    selector_border.x = x


update_selector()

# ===== ブロック名 =====
block_text = Text(
    text='',
    parent=camera.ui,
    position=(-0.85, -0.45),
    scale=1.5,
    color=color.white,
)


def update_block_text():
    block_text.text = f'Block: {BLOCK_TYPES[selected_block][0]}'


update_block_text()

# 現在のワールド名表示
world_name = os.path.basename(SAVE_PATH)[:-5]
Text(
    text=f'World: {world_name}',
    parent=camera.ui,
    position=(-0.85, 0.45),
    scale=1.2,
    color=color.white,
)


# ===== macOS描画バグ対策 =====
def force_redraw():
    props = app.win.getProperties()
    w = props.getXSize()
    h = props.getYSize()
    new_props = WindowProperties()
    new_props.setSize(w + 1, h + 1)
    app.win.requestProperties(new_props)
    invoke(restore_size, w=w, h=h, delay=0.03)


def restore_size(w, h):
    new_props = WindowProperties()
    new_props.setSize(w, h)
    app.win.requestProperties(new_props)


invoke(force_redraw, delay=0.5)

# ===== プレイヤー =====
WORLD_SIZE = 70
player = Entity(position=(WORLD_SIZE / 2, 3, WORLD_SIZE / 2))
camera.parent = player
camera.position = (0, 1.5, 0)
camera.rotation = (0, 0, 0)
camera.fov = 90

PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.3

# ===== ブロック選択枠 =====
selection_frame = Entity(enabled=False)
_v = 0.501
_t = 0.015

Entity(parent=selection_frame, model='cube', color=color.black,
       position=(0, -_v, -_v), scale=(2 * _v + _t, _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(0, -_v,  _v), scale=(2 * _v + _t, _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(-_v, -_v, 0), scale=(_t, _t, 2 * _v + _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(_v, -_v, 0), scale=(_t, _t, 2 * _v + _t))

Entity(parent=selection_frame, model='cube', color=color.black,
       position=(0, _v, -_v), scale=(2 * _v + _t, _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(0, _v,  _v), scale=(2 * _v + _t, _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(-_v, _v, 0), scale=(_t, _t, 2 * _v + _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(_v, _v, 0), scale=(_t, _t, 2 * _v + _t))

Entity(parent=selection_frame, model='cube', color=color.black,
       position=(-_v, 0, -_v), scale=(_t, 2 * _v + _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(_v, 0, -_v), scale=(_t, 2 * _v + _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(-_v, 0,  _v), scale=(_t, 2 * _v + _t, _t))
Entity(parent=selection_frame, model='cube', color=color.black,
       position=(_v, 0,  _v), scale=(_t, 2 * _v + _t, _t))

# ===== 地形 =====
boxes = []


def place_block(x, y, z, block_id):
    name, col, tex = BLOCK_TYPES[block_id]
    b = Button(color=col, model='cube',
               position=(x, y, z),
               texture=tex, parent=scene, origin_y=0.5,
               collider='box')
    if b.texture:
        b.texture.filtering = None
    b.block_type = block_id
    boxes.append(b)
    return b


# ===== セーブ / ロード =====
def save_world():
    data = {
        'blocks': [[int(b.x), int(b.y), int(b.z), b.block_type] for b in boxes],
        'player': [player.x, player.y, player.z],
    }
    with open(SAVE_PATH, 'w') as f:
        json.dump(data, f)
    print(f'saved: {SAVE_PATH}')


def load_world():
    with open(SAVE_PATH) as f:
        data = json.load(f)
    for bx, by, bz, bid in data['blocks']:
        place_block(bx, by, bz, bid)
    px, py, pz = data['player']
    player.position = (px, py, pz)
    print(f'loaded: {SAVE_PATH}')


def generate_new_world():
    for i in range(WORLD_SIZE):
        for j in range(WORLD_SIZE):
            place_block(j, 0, i, 0)


if IS_NEW:
    generate_new_world()
else:
    load_world()

# ===== 状態 =====
yaw = 0
pitch = 0
sensitivity = 0.2
move_speed = 6

velocity_horizontal = Vec3(0, 0, 0)
FRICTION = 12

SNEAK_MUL = 0.55
SPRINT_MUL = 1.6

gravity_on = False
velocity_y = 0
GRAVITY = 25
JUMP_POWER = 9
space_cooldown = 0
DOUBLE_TAP = 0.3

click_cooldown = 0
CLICK_INTERVAL = 0.15

scroll_cooldown = 0
SCROLL_INTERVAL = 0.15

REACH = 5
STANDING_REACH = 0.4
first_frame = True

# 距離カリング
RENDER_DISTANCE = 25
cull_counter = 0


def get_center():
    w = app.win.getProperties().getXSize()
    h = app.win.getProperties().getYSize()
    return w // 2, h // 2


def player_bounds():
    return {
        'min_x': player.x - PLAYER_RADIUS,
        'max_x': player.x + PLAYER_RADIUS,
        'min_y': player.y,
        'max_y': player.y + PLAYER_HEIGHT,
        'min_z': player.z - PLAYER_RADIUS,
        'max_z': player.z + PLAYER_RADIUS,
    }


def block_overlaps_player(block_pos):
    XZ_MARGIN = 0.11
    p_min_x = player.x - PLAYER_RADIUS - XZ_MARGIN
    p_max_x = player.x + PLAYER_RADIUS + XZ_MARGIN
    p_min_y = player.y
    p_max_y = player.y + PLAYER_HEIGHT
    p_min_z = player.z - PLAYER_RADIUS - XZ_MARGIN
    p_max_z = player.z + PLAYER_RADIUS + XZ_MARGIN

    b_min_x = block_pos.x - 0.5
    b_max_x = block_pos.x + 0.5
    b_min_y = block_pos.y - 1
    b_max_y = block_pos.y
    b_min_z = block_pos.z - 0.5
    b_max_z = block_pos.z + 0.5

    return (
        p_min_x < b_max_x and
        p_max_x > b_min_x and
        p_min_y < b_max_y and
        p_max_y > b_min_y and
        p_min_z < b_max_z and
        p_max_z > b_min_z
    )


def is_above_standing_block(new_pos):
    ground_check = raycast(
        player.world_position + Vec3(0, 0.05, 0),
        Vec3(0, -1, 0),
        distance=0.15,
        ignore=[player],
    )
    if not ground_check.hit:
        return False

    under_hit = raycast(
        player.world_position + Vec3(0, 0.1, 0),
        Vec3(0, -1, 0),
        distance=2,
        ignore=[player],
    )
    if not under_hit.hit:
        return False

    sb = under_hit.entity
    return (
        abs(new_pos.x - sb.x) < 0.1 and
        abs(new_pos.z - sb.z) < 0.1 and
        abs(new_pos.y - (sb.y + 1)) < 0.1
    )


def try_move_axis(axis, delta, sneak=False):
    if delta == 0:
        return True

    if axis == 'x':
        direction = Vec3(1 if delta > 0 else -1, 0, 0)
    else:
        direction = Vec3(0, 0, 1 if delta > 0 else -1)

    heights = [0.1, PLAYER_HEIGHT / 2, PLAYER_HEIGHT - 0.1]
    if axis == 'x':
        perp_offsets = [
            Vec3(0, 0, -PLAYER_RADIUS + 0.01),
            Vec3(0, 0, 0),
            Vec3(0, 0, PLAYER_RADIUS - 0.01),
        ]
    else:
        perp_offsets = [
            Vec3(-PLAYER_RADIUS + 0.01, 0, 0),
            Vec3(0, 0, 0),
            Vec3(PLAYER_RADIUS - 0.01, 0, 0),
        ]

    dist = PLAYER_RADIUS + abs(delta)

    for h in heights:
        for off in perp_offsets:
            origin = player.world_position + Vec3(0, h, 0) + off
            hit = raycast(origin, direction, distance=dist, ignore=[player])
            if hit.hit:
                return False

    if sneak and gravity_on:
        r_check = PLAYER_RADIUS - 0.02

        on_ground = False
        for ox, oz in [(0, 0), (r_check, 0), (-r_check, 0),
                       (0, r_check), (0, -r_check),
                       (r_check, r_check), (-r_check, r_check),
                       (r_check, -r_check), (-r_check, -r_check)]:
            gc = raycast(
                player.world_position + Vec3(ox, 0.1, oz),
                Vec3(0, -1, 0),
                distance=0.3,
                ignore=[player],
            )
            if gc.hit:
                on_ground = True
                break

        if on_ground:
            new_x = player.x + (delta if axis == 'x' else 0)
            new_z = player.z + (delta if axis == 'z' else 0)

            can_stand_after = False
            for ox, oz in [(0, 0), (r_check, 0), (-r_check, 0),
                           (0, r_check), (0, -r_check),
                           (r_check, r_check), (-r_check, r_check),
                           (r_check, -r_check), (-r_check, -r_check)]:
                hit = raycast(
                    Vec3(new_x + ox, player.y + 0.1, new_z + oz),
                    Vec3(0, -1, 0),
                    distance=0.3,
                    ignore=[player],
                )
                if hit.hit:
                    can_stand_after = True
                    break

            if not can_stand_after:
                return False

    if axis == 'x':
        player.x += delta
    else:
        player.z += delta
    return True


def update():
    global yaw, pitch, space_cooldown, velocity_y, first_frame
    global click_cooldown, scroll_cooldown, velocity_horizontal, cull_counter

    cx, cy = get_center()

    if first_frame:
        app.win.movePointer(0, cx, cy)
        first_frame = False
        return

    md = app.win.getPointer(0)
    dx_m = md.getX() - cx
    dy_m = md.getY() - cy

    yaw += dx_m * sensitivity
    pitch += dy_m * sensitivity
    pitch = max(-90, min(90, pitch))

    player.rotation_y = yaw
    camera.rotation_x = pitch

    app.win.movePointer(0, cx, cy)

    space_cooldown = max(0, space_cooldown - time.dt)
    click_cooldown = max(0, click_cooldown - time.dt)
    scroll_cooldown = max(0, scroll_cooldown - time.dt)

    forward = player.forward
    right = player.right
    input_dir = (forward * (held_keys['w'] - held_keys['s'])
                 + right * (held_keys['d'] - held_keys['a']))
    input_dir = Vec3(input_dir.x, 0, input_dir.z)
    if input_dir.length() > 0:
        input_dir = input_dir.normalized()

    sneak = held_keys['left shift'] or held_keys['right shift']
    sprint = held_keys['left control'] or held_keys['right control']

    current_speed = move_speed
    if sneak and gravity_on:
        current_speed *= SNEAK_MUL
    if sprint:
        current_speed *= SPRINT_MUL

    friction = FRICTION
    if sneak and gravity_on:
        friction = FRICTION * 2

    target_velocity = input_dir * current_speed
    lerp_t = min(1, friction * time.dt)
    velocity_horizontal += (target_velocity - velocity_horizontal) * lerp_t

    step_v = velocity_horizontal * time.dt
    moved_x = try_move_axis('x', step_v.x, sneak=sneak)
    moved_z = try_move_axis('z', step_v.z, sneak=sneak)

    if not moved_x:
        velocity_horizontal = Vec3(0, velocity_horizontal.y, velocity_horizontal.z)
    if not moved_z:
        velocity_horizontal = Vec3(velocity_horizontal.x, velocity_horizontal.y, 0)

    if gravity_on:
        check_points = [
            (0, 0),
            (PLAYER_RADIUS - 0.02, 0),
            (-PLAYER_RADIUS + 0.02, 0),
            (0, PLAYER_RADIUS - 0.02),
            (0, -PLAYER_RADIUS + 0.02),
            (PLAYER_RADIUS - 0.02, PLAYER_RADIUS - 0.02),
            (-PLAYER_RADIUS + 0.02, PLAYER_RADIUS - 0.02),
            (PLAYER_RADIUS - 0.02, -PLAYER_RADIUS + 0.02),
            (-PLAYER_RADIUS + 0.02, -PLAYER_RADIUS + 0.02),
        ]

        ground_y = -9999
        for ox, oz in check_points:
            hit = raycast(
                player.world_position + Vec3(ox, 0.1, oz),
                Vec3(0, -1, 0),
                distance=100,
                ignore=[player],
            )
            if hit.hit and hit.world_point.y > ground_y:
                ground_y = hit.world_point.y

        velocity_y -= GRAVITY * time.dt
        player.y += velocity_y * time.dt

        if velocity_y > 0:
            hit_up = raycast(
                player.world_position + Vec3(0, PLAYER_HEIGHT - 0.1, 0),
                Vec3(0, 1, 0),
                distance=0.3,
                ignore=[player],
            )
            if hit_up.hit:
                velocity_y = 0

        if player.y <= ground_y:
            player.y = ground_y
            velocity_y = 0
            if held_keys['space'] and not sneak:
                velocity_y = JUMP_POWER
    else:
        dy = time.dt * move_speed
        corners = [
            (PLAYER_RADIUS - 0.02, PLAYER_RADIUS - 0.02),
            (-PLAYER_RADIUS + 0.02, PLAYER_RADIUS - 0.02),
            (PLAYER_RADIUS - 0.02, -PLAYER_RADIUS + 0.02),
            (-PLAYER_RADIUS + 0.02, -PLAYER_RADIUS + 0.02),
        ]

        if held_keys['space']:
            blocked = False
            for ox, oz in corners:
                hit = raycast(
                    player.world_position + Vec3(ox, PLAYER_HEIGHT, oz),
                    Vec3(0, 1, 0),
                    distance=dy + 0.05,
                    ignore=[player],
                )
                if hit.hit:
                    blocked = True
                    break
            if not blocked:
                player.y += dy

        if sneak:
            blocked = False
            for ox, oz in corners:
                hit = raycast(
                    player.world_position + Vec3(ox, 0.05, oz),
                    Vec3(0, -1, 0),
                    distance=dy + 0.05,
                    ignore=[player],
                )
                if hit.hit:
                    blocked = True
                    break
            if not blocked:
                player.y -= dy

    # 選択枠
    sel_hit = raycast(
        camera.world_position,
        camera.forward,
        distance=REACH,
        ignore=[player],
    )
    if sel_hit.hit and sel_hit.entity in boxes:
        selection_frame.enabled = True
        e = sel_hit.entity
        selection_frame.position = Vec3(e.x, e.y - 0.5, e.z)
    else:
        selection_frame.enabled = False

    # 距離カリング
    cull_counter = (cull_counter + 1) % 5
    if cull_counter == 0:
        px, pz = player.x, player.z
        rd2 = RENDER_DISTANCE ** 2
        for b in boxes:
            dx = b.x - px
            dz = b.z - pz
            b.enabled = (dx * dx + dz * dz) < rd2

    if player.y < -30:
        player.position = (WORLD_SIZE / 2, 3, WORLD_SIZE / 2)
        velocity_y = 0
        velocity_horizontal = Vec3(0, 0, 0)


def input(key):
    global gravity_on, velocity_y, space_cooldown
    global click_cooldown, selected_block, scroll_cooldown

    if key == 'escape':
        save_world()
        application.quit()
        return

    if key.isdigit():
        idx = int(key) - 1
        if 0 <= idx < len(BLOCK_TYPES):
            selected_block = idx
            update_selector()
            update_block_text()
            return

    if key == 'scroll up':
        if scroll_cooldown > 0:
            return
        scroll_cooldown = SCROLL_INTERVAL
        selected_block = (selected_block + 1) % len(BLOCK_TYPES)
        update_selector()
        update_block_text()
        return
    if key == 'scroll down':
        if scroll_cooldown > 0:
            return
        scroll_cooldown = SCROLL_INTERVAL
        selected_block = (selected_block - 1) % len(BLOCK_TYPES)
        update_selector()
        update_block_text()
        return

    if key == 'space':
        if space_cooldown > 0:
            gravity_on = not gravity_on
            velocity_y = 0
        space_cooldown = DOUBLE_TAP

    if key not in ('left mouse down', 'right mouse down'):
        return

    if click_cooldown > 0:
        return
    click_cooldown = CLICK_INTERVAL

    hit = raycast(
        camera.world_position,
        camera.forward,
        distance=REACH,
        ignore=[player],
    )
    if not hit.hit or hit.entity not in boxes:
        return

    target = hit.entity

    if key == 'left mouse down':
        new_pos = target.position + hit.normal

        if block_overlaps_player(new_pos):
            return

        if is_above_standing_block(new_pos):
            return

        place_block(new_pos.x, new_pos.y, new_pos.z, selected_block)

    if key == 'right mouse down':
        boxes.remove(target)
        destroy(target)


app.run()