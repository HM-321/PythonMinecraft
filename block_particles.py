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
        block_id = getattr(block, 'block_type', None)
        if block_id is None or not 0 <= block_id < len(BLOCK_TYPES):
            return

        _, block_color, texture_info = BLOCK_TYPES[block_id]
        texture_path = texture_info
        if isinstance(texture_info, dict):
            texture_path = texture_info.get('atlas')

        for _ in range(amount):
            particle = Entity(
                model='quad',
                color=self._random_pixel(texture_path, block_color),
                position=block.position + Vec3(
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
