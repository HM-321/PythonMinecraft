from ursina import Entity, Vec3, camera, raycast, held_keys, time
from settings import settings
from voxel_collision import (
    _world, overlaps_player, supporting_top, sweep_vertical,
)
from config import (PLAYER_HEIGHT, PLAYER_RADIUS,
                    MOVE_SPEED, SNEAK_MUL, SPRINT_MUL, FRICTION,
                    GRAVITY, JUMP_POWER, SENSITIVITY, DOUBLE_TAP,
                    WORLD_SIZE)


class PlayerController:
    def __init__(self, spawn_pos):
        self.entity = Entity(position=spawn_pos)
        camera.parent = self.entity
        camera.position = (0, 1.5, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = settings.get('fov')

        self.yaw = 0
        self.pitch = 0
        self.velocity_h = Vec3(0, 0, 0)
        self.velocity_y = 0
        self.gravity_on = True
        self.space_cd = 0
        self.spawn_pos = spawn_pos
        self.sneaking = False

    def block_overlaps(self, pos):
        p = self.entity
        return (
            p.x - PLAYER_RADIUS < pos.x + 0.5 and
            p.x + PLAYER_RADIUS > pos.x - 0.5 and
            p.y < pos.y and
            p.y + PLAYER_HEIGHT > pos.y - 1 and
            p.z - PLAYER_RADIUS < pos.z + 0.5 and
            p.z + PLAYER_RADIUS > pos.z - 0.5
        )

    def is_above_standing_block(self, pos):
        p = self.entity
        world = _world()
        ground_y = supporting_top(
            world, p.x, p.y, p.z, PLAYER_RADIUS - 0.02, max_drop=0.18
        )
        if ground_y is None:
            return False
        return (
            abs(pos.x - round(p.x)) < 0.6
            and abs(pos.z - round(p.z)) < 0.6
            and abs(pos.y - (ground_y + 1)) < 0.1
        )

    def try_move_axis(self, axis, delta, sneak=False):
        if delta == 0:
            return True
        p = self.entity
        world = _world()
        next_x = p.x + (delta if axis == 'x' else 0)
        next_z = p.z + (delta if axis == 'z' else 0)

        if overlaps_player(
            world, next_x, p.y, next_z, PLAYER_RADIUS, PLAYER_HEIGHT
        ):
            return False

        if sneak and self.gravity_on:
            on_ground = supporting_top(
                world, p.x, p.y, p.z,
                PLAYER_RADIUS - 0.02, max_drop=0.18,
            ) is not None
            can_stand = supporting_top(
                world, next_x, p.y, next_z,
                PLAYER_RADIUS - 0.02, max_drop=0.22,
            ) is not None
            if on_ground and not can_stand:
                return False

        if axis == 'x':
            p.x = next_x
        else:
            p.z = next_z
        return True


    def update_view(self, dx_mouse, dy_mouse):
        from settings import settings
        sens = settings.get('sensitivity')
        self.yaw += dx_mouse * sens
        self.pitch += dy_mouse * sens
        self.pitch = max(-90, min(90, self.pitch))
        self.entity.rotation_y = self.yaw
        camera.rotation_x = self.pitch
    
    
    def _update_camera_offset(self, sneak):
        """スニーク中はカメラを少し下げる"""
        target_y = 1.5 if not sneak else 1.2
        # 補間で滑らかに
        current = camera.y
        camera.y += (target_y - current) * min(1, 15 * time.dt)
        
    def update_movement(self):
        p = self.entity
        forward = p.forward
        right = p.right

        # キーボード入力
        kb_x = held_keys['d'] - held_keys['a']
        kb_z = held_keys['w'] - held_keys['s']

        # コントローラー入力
        import __main__
        c_x = 0
        c_z = 0
        if hasattr(__main__, 'controller') and __main__.controller.is_connected():
            c_x = __main__.controller.move_x()
            c_z = -__main__.controller.move_y()

        input_x = kb_x + c_x
        input_z = kb_z + c_z

        input_dir = forward * input_z + right * input_x
        input_dir = Vec3(input_dir.x, 0, input_dir.z)
        if input_dir.length() > 0:
            input_dir = input_dir.normalized()

        sneak_key = settings.get('key_sneak')
        sprint_key = settings.get('key_sprint')
        sneak = bool(sneak_key and held_keys[sneak_key])
        sprint = bool(sprint_key and held_keys[sprint_key])

        if hasattr(__main__, 'controller') and __main__.controller.is_connected():
            c = __main__.controller
            if c.button_held(settings.get('ctrl_sneak')):
                sneak = True
            if c.button_held(settings.get('ctrl_dash')):
                sprint = True
                

        # 現在のスニーク状態をマルチプレイへ送れるよう保持する。
        self.sneaking = bool(sneak)

        speed = MOVE_SPEED
        if sneak and self.gravity_on:
            speed *= SNEAK_MUL
        if sprint:
            speed *= SPRINT_MUL

        friction = FRICTION * 2 if (sneak and self.gravity_on) else FRICTION
        target = input_dir * speed
        lerp_t = min(1, friction * time.dt)
        self.velocity_h += (target - self.velocity_h) * lerp_t

        step = self.velocity_h * time.dt
        moved_x = self.try_move_axis('x', step.x, sneak=sneak)
        moved_z = self.try_move_axis('z', step.z, sneak=sneak)

        if not moved_x:
            self.velocity_h = Vec3(0, self.velocity_h.y, self.velocity_h.z)
        if not moved_z:
            self.velocity_h = Vec3(self.velocity_h.x, self.velocity_h.y, 0)

        self._update_vertical(sneak)
        self._update_camera_offset(sneak)

    def _update_vertical(self, sneak):
        p = self.entity
        import __main__

        jump_key = settings.get('key_jump')
        jump_input = bool(jump_key and held_keys[jump_key])
        if hasattr(__main__, 'controller') and __main__.controller.is_connected():
            if __main__.controller.button_held(settings.get('ctrl_jump')):
                jump_input = True

        world = _world()
        dt = min(time.dt, 0.05)

        if self.gravity_on:
            grounded = supporting_top(
                world, p.x, p.y, p.z,
                PLAYER_RADIUS - 0.02, max_drop=0.18,
            )
            if grounded is not None and self.velocity_y <= 0:
                p.y = grounded
                self.velocity_y = 0
                if jump_input:
                    self.velocity_y = JUMP_POWER

            self.velocity_y -= GRAVITY * dt
            next_y, collided = sweep_vertical(
                world, p.x, p.y, p.z,
                PLAYER_RADIUS - 0.02, PLAYER_HEIGHT,
                self.velocity_y * dt,
            )
            p.y = next_y
            if collided:
                self.velocity_y = 0
        else:
            dy = dt * MOVE_SPEED
            if jump_input:
                next_y, _ = sweep_vertical(
                    world, p.x, p.y, p.z,
                    PLAYER_RADIUS - 0.02, PLAYER_HEIGHT, dy,
                )
                p.y = next_y
            if sneak:
                next_y, _ = sweep_vertical(
                    world, p.x, p.y, p.z,
                    PLAYER_RADIUS - 0.02, PLAYER_HEIGHT, -dy,
                )
                p.y = next_y

        if p.y < -30:
            p.position = self._find_safe_respawn()
            self.velocity_y = 0
            self.velocity_h = Vec3(0, 0, 0)

    def _find_safe_respawn(self):
        world = _world()
        if not world or not world.block_data_by_position:
            return self.spawn_pos

        columns = {}
        for x, y, z in world.block_data_by_position:
            columns.setdefault((x, z), []).append(y)

        origin_x = round(self.entity.x)
        origin_z = round(self.entity.z)
        max_radius = max(WORLD_SIZE, 32)
        for radius in range(max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if max(abs(dx), abs(dz)) != radius:
                        continue
                    x = origin_x + dx
                    z = origin_z + dz
                    for ground_y in sorted(columns.get((x, z), ()), reverse=True):
                        if not world.has_block(x, ground_y + 1, z) and not world.has_block(
                            x, ground_y + 2, z
                        ):
                            return Vec3(x, ground_y, z)
        return self.spawn_pos

    def tick(self, dt):
        self.space_cd = max(0, self.space_cd - dt)

    def try_toggle_gravity(self):
        if self.space_cd > 0:
            self.gravity_on = not self.gravity_on
            self.velocity_y = 0
        self.space_cd = DOUBLE_TAP