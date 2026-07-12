from ursina import Entity, Vec3, camera, raycast, held_keys, time
from settings import settings
from config import (PLAYER_HEIGHT, PLAYER_RADIUS,
                    MOVE_SPEED, SNEAK_MUL, SPRINT_MUL, FRICTION,
                    GRAVITY, JUMP_POWER, SENSITIVITY, DOUBLE_TAP)


class PlayerController:
    def __init__(self, spawn_pos):
        self.entity = Entity(position=spawn_pos)
        camera.parent = self.entity
        camera.position = (0, 1.5, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = 90

        self.yaw = 0
        self.pitch = 0
        self.velocity_h = Vec3(0, 0, 0)
        self.velocity_y = 0
        self.gravity_on = True
        self.space_cd = 0
        self.spawn_pos = spawn_pos

    def block_overlaps(self, pos):
        XZ = 0.11
        p = self.entity
        return (
            p.x - PLAYER_RADIUS - XZ < pos.x + 0.5 and
            p.x + PLAYER_RADIUS + XZ > pos.x - 0.5 and
            p.y < pos.y and
            p.y + PLAYER_HEIGHT > pos.y - 1 and
            p.z - PLAYER_RADIUS - XZ < pos.z + 0.5 and
            p.z + PLAYER_RADIUS + XZ > pos.z - 0.5
        )

    def is_above_standing_block(self, pos):
        p = self.entity
        gc = raycast(p.world_position + Vec3(0, 0.05, 0),
                     Vec3(0, -1, 0), distance=0.15, ignore=[p])
        if not gc.hit:
            return False
        uh = raycast(p.world_position + Vec3(0, 0.1, 0),
                     Vec3(0, -1, 0), distance=2, ignore=[p])
        if not uh.hit:
            return False
        sb = uh.entity
        return (abs(pos.x - sb.x) < 0.1 and
                abs(pos.z - sb.z) < 0.1 and
                abs(pos.y - (sb.y + 1)) < 0.1)

    def try_move_axis(self, axis, delta, sneak=False):
        if delta == 0:
            return True
        p = self.entity

        if axis == 'x':
            direction = Vec3(1 if delta > 0 else -1, 0, 0)
            perp = [Vec3(0, 0, -PLAYER_RADIUS + 0.01), Vec3(0, 0, 0),
                    Vec3(0, 0, PLAYER_RADIUS - 0.01)]
        else:
            direction = Vec3(0, 0, 1 if delta > 0 else -1)
            perp = [Vec3(-PLAYER_RADIUS + 0.01, 0, 0), Vec3(0, 0, 0),
                    Vec3(PLAYER_RADIUS - 0.01, 0, 0)]

        heights = [0.1, PLAYER_HEIGHT / 2, PLAYER_HEIGHT - 0.1]
        dist = PLAYER_RADIUS + abs(delta)

        for h in heights:
            for off in perp:
                origin = p.world_position + Vec3(0, h, 0) + off
                hit = raycast(origin, direction, distance=dist, ignore=[p])
                if hit.hit:
                    return False

        if sneak and self.gravity_on:
            r = PLAYER_RADIUS - 0.02
            offsets = [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r),
                       (r, r), (-r, r), (r, -r), (-r, -r)]

            on_ground = False
            for ox, oz in offsets:
                if raycast(p.world_position + Vec3(ox, 0.1, oz),
                           Vec3(0, -1, 0), distance=0.3, ignore=[p]).hit:
                    on_ground = True
                    break

            if on_ground:
                new_x = p.x + (delta if axis == 'x' else 0)
                new_z = p.z + (delta if axis == 'z' else 0)
                can_stand = False
                for ox, oz in offsets:
                    if raycast(Vec3(new_x + ox, p.y + 0.1, new_z + oz),
                               Vec3(0, -1, 0), distance=0.3, ignore=[p]).hit:
                        can_stand = True
                        break
                if not can_stand:
                    return False

        if axis == 'x':
            p.x += delta
        else:
            p.z += delta
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

        sneak = held_keys['left shift'] or held_keys['right shift']
        sprint = held_keys['left control'] or held_keys['right control']

        if hasattr(__main__, 'controller') and __main__.controller.is_connected():
            c = __main__.controller
            # Bボタンでしゃがみ
            if c.button_held(c.BTN_B):
                sneak = True
            # 左スティック押し込みでダッシュ
            if c.button_held(c.BTN_LSTICK):
                sprint = True

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
        
        # ジャンプ入力（キーボード or Aボタン押しっぱなし = OK）
        jump_input = held_keys[settings.get('key_jump')]
        if hasattr(__main__, 'controller') and __main__.controller.is_connected():
            if __main__.controller.button_held(__main__.controller.BTN_A):
                jump_input = True

        if self.gravity_on:
            r = PLAYER_RADIUS - 0.02
            pts = [(0, 0), (r, 0), (-r, 0), (0, r), (0, -r),
                (r, r), (-r, r), (r, -r), (-r, -r)]
            ground_y = -9999
            for ox, oz in pts:
                hit = raycast(p.world_position + Vec3(ox, 0.1, oz),
                            Vec3(0, -1, 0), distance=100, ignore=[p])
                if hit.hit and hit.world_point.y > ground_y:
                    ground_y = hit.world_point.y

            self.velocity_y -= GRAVITY * time.dt

            # 頭上判定
            if self.velocity_y > 0:
                r = PLAYER_RADIUS - 0.02
                corners = [(0, 0), (r, r), (-r, r), (r, -r), (-r, -r)]
                check_dist = self.velocity_y * time.dt + 0.05
                for ox, oz in corners:
                    origin = p.world_position + Vec3(ox, PLAYER_HEIGHT, oz)
                    hu = raycast(origin, Vec3(0, 1, 0), distance=check_dist, ignore=[p])
                    if hu.hit:
                        p.y = hu.world_point.y - PLAYER_HEIGHT - 0.01
                        self.velocity_y = 0
                        break

            p.y += self.velocity_y * time.dt

            if p.y <= ground_y:
                p.y = ground_y
                self.velocity_y = 0
                if jump_input and not sneak:
                    self.velocity_y = JUMP_POWER
        else:
            dy = time.dt * MOVE_SPEED
            r = PLAYER_RADIUS - 0.02
            corners = [(r, r), (-r, r), (r, -r), (-r, -r)]
            
            if jump_input:
                if not any(raycast(
                        p.world_position + Vec3(ox, PLAYER_HEIGHT, oz),
                        Vec3(0, 1, 0), distance=dy + 0.05, ignore=[p]).hit
                        for ox, oz in corners):
                    p.y += dy
            
            if sneak:
                if not any(raycast(
                        p.world_position + Vec3(ox, 0.05, oz),
                        Vec3(0, -1, 0), distance=dy + 0.05, ignore=[p]).hit
                        for ox, oz in corners):
                    p.y -= dy

        if p.y < -30:
            p.position = self.spawn_pos
            self.velocity_y = 0
            self.velocity_h = Vec3(0, 0, 0)
        
    def tick(self, dt):
        self.space_cd = max(0, self.space_cd - dt)

    def try_toggle_gravity(self):
        if self.space_cd > 0:
            self.gravity_on = not self.gravity_on
            self.velocity_y = 0
        self.space_cd = DOUBLE_TAP