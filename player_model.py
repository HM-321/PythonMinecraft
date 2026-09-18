from math import atan2, degrees, exp, sin

from ursina import Entity, color, destroy


PLAYER_COLORS = (
    color.rgb(24, 82, 126),
    color.orange,
    color.lime,
    color.magenta,
)


class RemotePlayer:
    """Lightweight third-person model for a remote network player."""

    def __init__(self, player_id, position=(0, 0, 0)):
        self.player_id = player_id
        self.root = Entity(position=position)

        # 頭は視点方向、胴体と手足は移動方向へ向ける。
        self.body_root = Entity(parent=self.root)

        player_color = PLAYER_COLORS[(int(player_id) - 1) % len(PLAYER_COLORS)]

        self.body = Entity(parent=self.body_root, model='cube', color=player_color,
                           scale=(0.45, 0.675, 0.225), y=1.0125)
        self.head = Entity(parent=self.root, model='cube', color=color.rgb(240, 190, 145),
                           scale=(0.45, 0.45, 0.45), y=1.575)
        hair_color = color.rgb(64, 38, 24)
        face_color = color.rgb(24, 18, 16)
        self.hair = Entity(parent=self.head, model='cube', color=hair_color,
                   scale=(1.1, 0.2, 1.1), y=0.44)
        self.left_hair = Entity(parent=self.head, model='cube', color=hair_color,
                    scale=(0.18, 0.55, 0.22), x=-0.45, y=0.16)
        self.right_hair = Entity(parent=self.head, model='cube', color=hair_color,
                     scale=(0.18, 0.55, 0.22), x=0.45, y=0.16)
        # 後頭部を覆って、遠くからでも頭の向きを判別しやすくする。
        self.back_hair = Entity(
            parent=self.head,
            model='cube',
            color=hair_color,
            scale=(0.92, 0.72, 0.08),
            y=0.04,
            z=-0.51,
        )
        self.left_eye = Entity(parent=self.head, model='cube', color=face_color,
                       scale=(0.13, 0.13, 0.04), x=-0.2, y=0.08, z=0.51)
        self.right_eye = Entity(parent=self.head, model='cube', color=face_color,
                    scale=(0.13, 0.13, 0.04), x=0.2, y=0.08, z=0.51)
        self.mouth_left = Entity(parent=self.head, model='cube', color=face_color,
                     scale=(0.16, 0.06, 0.04), x=-0.09,
                     y=-0.15, z=0.51, rotation_z=-25)
        self.mouth_right = Entity(parent=self.head, model='cube', color=face_color,
                      scale=(0.16, 0.06, 0.04), x=0.09,
                      y=-0.15, z=0.51, rotation_z=25)
        self.left_arm = Entity(
            parent=self.body_root,
            model='cube',
            color=player_color,
            scale=(0.225, 0.675, 0.225),
            origin_y=0.5,
            x=-0.3375,
            y=1.35,
        )
        self.right_arm = Entity(
            parent=self.body_root,
            model='cube',
            color=player_color,
            scale=(0.225, 0.675, 0.225),
            origin_y=0.5,
            x=0.3375,
            y=1.35,
        )
        self.left_leg = Entity(
            parent=self.body_root,
            model='cube',
            color=color.dark_gray,
            scale=(0.225, 0.675, 0.225),
            origin_y=0.5,
            x=-0.1125,
            y=0.675,
        )
        self.right_leg = Entity(
            parent=self.body_root,
            model='cube',
            color=color.dark_gray,
            scale=(0.225, 0.675, 0.225),
            origin_y=0.5,
            x=0.1125,
            y=0.675,
        )
        self._parts = (self.body, self.head, self.left_arm, self.right_arm,
                       self.left_leg, self.right_leg)
        self._walk_time = 0.0
        self._moving = False
        self._sneaking = False
        self._last_position = None
        self._body_yaw_offset = 0.0

    def _apply_sneak_visual(self, sneaking):
        if sneaking == self._sneaking:
            return

        self._sneaking = sneaking

        if sneaking:
            self.body.scale = (0.45, 0.56, 0.225)
            self.body.y = 0.9

            self.head.scale = (0.45, 0.45, 0.45)
            self.head.y = 1.4

            self.left_arm.scale = (0.225, 0.56, 0.225)
            self.left_arm.y = 1.18
            self.right_arm.scale = (0.225, 0.56, 0.225)
            self.right_arm.y = 1.18

            self.left_leg.scale = (0.225, 0.62, 0.225)
            self.left_leg.y = 0.62
            self.right_leg.scale = (0.225, 0.62, 0.225)
            self.right_leg.y = 0.62
        else:
            self.body.scale = (0.45, 0.675, 0.225)
            self.body.y = 1.0125

            self.head.scale = (0.45, 0.45, 0.45)
            self.head.y = 1.575

            self.left_arm.scale = (0.225, 0.675, 0.225)
            self.left_arm.y = 1.35
            self.right_arm.scale = (0.225, 0.675, 0.225)
            self.right_arm.y = 1.35

            self.left_leg.scale = (0.225, 0.675, 0.225)
            self.left_leg.y = 0.675
            self.right_leg.scale = (0.225, 0.675, 0.225)
            self.right_leg.y = 0.675

    def update(self, position, yaw=0, pitch=0, moving=False, sneaking=False, dt=0):
        # 受信座標の差から水平速度を求め、歩行周期へ反映する。
        # テレポートやワールド再生成直後の大きな差分は無視する。
        planar_speed = 0.0
        movement_yaw = None

        if self._last_position is not None and dt > 0:
            dx = float(position[0]) - float(self._last_position[0])
            dz = float(position[2]) - float(self._last_position[2])
            distance = (dx * dx + dz * dz) ** 0.5

            if distance < 2.0:
                planar_speed = distance / dt

                if distance > 0.0001:
                    movement_yaw = degrees(atan2(dx, dz))

        self._last_position = tuple(position)
        self.root.position = position

        # rootと頭はカメラの向きを維持する。
        self.root.rotation_y = yaw
        self.head.rotation_x = max(-90, min(90, pitch))

        # 胴体と手足だけを実際の移動方向へ向ける。
        if moving and movement_yaw is not None:
            movement_offset = (
                movement_yaw - float(yaw) + 180.0
            ) % 360.0 - 180.0

            # 後方へ進むほど胴体を正面へ戻す。
            # 横90度から後方180度まで連続的に補間し、
            # 後ろ斜め移動で判定境界をまたいだ際の急回転を防ぐ。
            offset_abs = abs(movement_offset)
            if offset_abs <= 90.0:
                target_offset = movement_offset
            else:
                target_offset = (
                    180.0 - offset_abs
                ) * (1.0 if movement_offset >= 0.0 else -1.0)
        else:
            target_offset = 0.0

        turn_delta = (
            target_offset - self._body_yaw_offset + 180.0
        ) % 360.0 - 180.0
        # 元の追従速度16.0の3倍。滑らかさを保ちつつ素早く向きを変える。
        turn_blend = 1.0 - exp(-48.0 * max(0.0, dt))

        self._body_yaw_offset += turn_delta * turn_blend
        self.body_root.rotation_y = self._body_yaw_offset

        # 頭はbody_rootの子ではないため、視点方向のままになる。
        self._moving = bool(moving)
        self._apply_sneak_visual(bool(sneaking))

        if self._moving:
            # 通常歩行は約9 rad/s、速い移動では最大13 rad/sにする。
            # スニーク中は周期と振り幅を抑える。
            speed_ratio = max(0.0, min(1.0, planar_speed / 5.5))
            if self._sneaking:
                cycle_speed = 39.0 + 9.0 * speed_ratio
                amplitude = 40.0
            else:
                cycle_speed = 57.0 + 21.0 * speed_ratio
                amplitude = 75.0 + 25.0 * speed_ratio

            self._walk_time += dt * cycle_speed
            swing = sin(self._walk_time) * amplitude
            targets = (swing, -swing, -swing, swing)
        else:
            targets = (0.0, 0.0, 0.0, 0.0)

        # FPSに依存せず、停止時も急に無姿勢へ戻らないよう補間する。
        blend = 1.0 - exp(-14.0 * max(0.0, dt))
        parts = (
            self.left_arm,
            self.right_arm,
            self.left_leg,
            self.right_leg,
        )
        for part, target in zip(parts, targets):
            part.rotation_x += (target - part.rotation_x) * blend

    def destroy(self):
        destroy(self.root)