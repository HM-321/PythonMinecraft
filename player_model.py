from math import sin

from ursina import Entity, color, destroy


PLAYER_COLORS = (
    color.azure,
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
                           scale=(0.6, 0.9, 0.35), y=1.25)
        self.head = Entity(parent=self.root, model='cube', color=color.rgb(240, 190, 145),
                           scale=(0.65, 0.65, 0.65), y=2.05)
        self.left_arm = Entity(parent=self.root, model='cube', color=player_color,
                               scale=(0.22, 0.85, 0.25), x=-0.43, y=1.25)
        self.right_arm = Entity(parent=self.root, model='cube', color=player_color,
                                scale=(0.22, 0.85, 0.25), x=0.43, y=1.25)
        self.left_leg = Entity(parent=self.root, model='cube', color=color.dark_gray,
                               scale=(0.25, 0.85, 0.28), x=-0.18, y=0.45)
        self.right_leg = Entity(parent=self.root, model='cube', color=color.dark_gray,
                                scale=(0.25, 0.85, 0.28), x=0.18, y=0.45)
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
            self.body.scale = (0.6, 0.62, 0.35)
            self.body.y = 1.05

            self.head.scale = (0.65, 0.65, 0.65)
            self.head.y = 1.65

            self.left_arm.scale = (0.22, 0.66, 0.25)
            self.left_arm.y = 1.05
            self.right_arm.scale = (0.22, 0.66, 0.25)
            self.right_arm.y = 1.05

            self.left_leg.scale = (0.25, 0.72, 0.28)
            self.left_leg.y = 0.36
            self.right_leg.scale = (0.25, 0.72, 0.28)
            self.right_leg.y = 0.36
        else:
            self.body.scale = (0.6, 0.9, 0.35)
            self.body.y = 1.25

            self.head.scale = (0.65, 0.65, 0.65)
            self.head.y = 2.05

            self.left_arm.scale = (0.22, 0.85, 0.25)
            self.left_arm.y = 1.25
            self.right_arm.scale = (0.22, 0.85, 0.25)
            self.right_arm.y = 1.25

            self.left_leg.scale = (0.25, 0.85, 0.28)
            self.left_leg.y = 0.45
            self.right_leg.scale = (0.25, 0.85, 0.28)
            self.right_leg.y = 0.45

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