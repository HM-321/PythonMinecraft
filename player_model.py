from math import sin

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
        player_color = PLAYER_COLORS[(int(player_id) - 1) % len(PLAYER_COLORS)]

        self.body = Entity(parent=self.root, model='cube', color=player_color,
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
        self.left_arm = Entity(parent=self.root, model='cube', color=player_color,
                               scale=(0.225, 0.675, 0.225), x=-0.3375, y=1.0125)
        self.right_arm = Entity(parent=self.root, model='cube', color=player_color,
                                scale=(0.225, 0.675, 0.225), x=0.3375, y=1.0125)
        self.left_leg = Entity(parent=self.root, model='cube', color=color.dark_gray,
                               scale=(0.225, 0.675, 0.225), x=-0.1125, y=0.3375)
        self.right_leg = Entity(parent=self.root, model='cube', color=color.dark_gray,
                                scale=(0.225, 0.675, 0.225), x=0.1125, y=0.3375)
        self._parts = (self.body, self.head, self.left_arm, self.right_arm,
                       self.left_leg, self.right_leg)
        self._walk_time = 0.0
        self._moving = False
        self._sneaking = False

    def _apply_sneak_visual(self, sneaking):
        if sneaking == self._sneaking:
            return

        self._sneaking = sneaking

        if sneaking:
            self.body.scale = (0.45, 0.5, 0.225)
            self.body.y = 0.925

            self.head.scale = (0.45, 0.45, 0.45)
            self.head.y = 1.4

            self.left_arm.scale = (0.225, 0.56, 0.225)
            self.left_arm.y = 0.925
            self.right_arm.scale = (0.225, 0.56, 0.225)
            self.right_arm.y = 0.925

            self.left_leg.scale = (0.225, 0.62, 0.225)
            self.left_leg.y = 0.31
            self.right_leg.scale = (0.225, 0.62, 0.225)
            self.right_leg.y = 0.31
        else:
            self.body.scale = (0.45, 0.675, 0.225)
            self.body.y = 1.0125

            self.head.scale = (0.45, 0.45, 0.45)
            self.head.y = 1.575

            self.left_arm.scale = (0.225, 0.675, 0.225)
            self.left_arm.y = 1.0125
            self.right_arm.scale = (0.225, 0.675, 0.225)
            self.right_arm.y = 1.0125

            self.left_leg.scale = (0.225, 0.675, 0.225)
            self.left_leg.y = 0.3375
            self.right_leg.scale = (0.225, 0.675, 0.225)
            self.right_leg.y = 0.3375

    def update(self, position, yaw=0, pitch=0, moving=False, sneaking=False, dt=0):
        self.root.position = position
        self.root.rotation_y = yaw
        self.head.rotation_x = max(-90, min(90, pitch))
        self._moving = moving
        self._apply_sneak_visual(bool(sneaking))
        if moving:
            self._walk_time += dt * 9
            swing = sin(self._walk_time) * 28
            self.left_arm.rotation_x = swing
            self.right_arm.rotation_x = -swing
            self.left_leg.rotation_x = -swing
            self.right_leg.rotation_x = swing
        else:
            self.left_arm.rotation_x = 0
            self.right_arm.rotation_x = 0
            self.left_leg.rotation_x = 0
            self.right_leg.rotation_x = 0

    def destroy(self):
        destroy(self.root)