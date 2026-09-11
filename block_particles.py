import os
import random

from PIL import Image
from ursina import Entity, Vec3, color, destroy, time

from block_types import BLOCK_TYPES
from config import resource_path


class BlockParticles:
    def __init__(self):
        self.particles = []
        self._images = {}

    def burst(self, block, amount=16):
        """既存互換ラッパー。"""
        block_id = getattr(block, 'block_type', None)
        position = getattr(block, 'block_position', None)
        if position is None:
            position = block.position
        self.burst_at(position, block_id, amount=amount)

    def burst_at(self, position, block_data, amount=16):
        """Entityではなく座標とBlockData/IDから破壊粒子を生成する。"""
        block_id = getattr(block_data, 'block_type', block_data)
        if block_id is None or not 0 <= int(block_id) < len(BLOCK_TYPES):
            return
        block_id = int(block_id)
        _, block_color, texture_info = BLOCK_TYPES[block_id]
        texture_path = texture_info
        if isinstance(texture_info, dict):
            texture_path = texture_info.get('atlas')
        base_position = Vec3(*position)
        # 論理Yはブロック上面。粒子中心はブロック中央へ合わせる。
        base_position.y -= 0.5
        for _ in range(amount):
            particle = Entity(
                model='quad',
                color=self._random_pixel(texture_path, block_color),
                position=base_position + Vec3(
                    random.uniform(-0.35, 0.35),
                    random.uniform(-0.35, 0.35),
                    random.uniform(-0.35, 0.35),
                ),
                scale=random.uniform(0.045, 0.08),
                billboard=True,
                collider=None,
            )
            self.particles.append({
                'entity': particle,
                'velocity': Vec3(
                    random.uniform(-1.4, 1.4),
                    random.uniform(1.2, 2.8),
                    random.uniform(-1.4, 1.4),
                ),
                'life': random.uniform(0.35, 0.55),
            })

    def update(self):
        dt = time.dt
        alive = []
        for particle in self.particles:
            particle['life'] -= dt
            if particle['life'] <= 0:
                destroy(particle['entity'])
                continue

            velocity = particle['velocity']
            velocity.y -= 7 * dt
            entity = particle['entity']
            entity.position += velocity * dt
            entity.alpha = min(1, particle['life'] * 3)
            alive.append(particle)

        self.particles = alive

    def clear(self):
        for particle in self.particles:
            destroy(particle['entity'])
        self.particles.clear()

    def _random_pixel(self, texture_path, fallback):
        if not texture_path:
            return fallback

        image = self._images.get(texture_path)
        if image is None:
            path = (
                texture_path
                if os.path.isabs(texture_path)
                else resource_path(texture_path)
            )
            try:
                image = Image.open(path).convert('RGBA')
                image.load()
            except (OSError, ValueError):
                return fallback
            self._images[texture_path] = image

        r, g, b, a = image.getpixel((
            random.randrange(image.width),
            random.randrange(image.height),
        ))
        return color.rgba(r / 255, g / 255, b / 255, a / 255)
