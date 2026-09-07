import math
import random


class TerrainGenerator:
    """有限ワールド向けの決定論的な表面地形生成器。"""

    def __init__(self, seed=0):
        self.seed = int(seed)

    def _random_at(self, x, z):
        value = (
            int(x) * 374761393
            + int(z) * 668265263
            + self.seed * 1442695040888963407
        ) & 0xFFFFFFFFFFFFFFFF
        return random.Random(value).uniform(-1.0, 1.0)

    @staticmethod
    def _smoothstep(value):
        return value * value * (3.0 - 2.0 * value)

    def _noise(self, x, z, scale):
        sx, sz = x / scale, z / scale
        x0, z0 = math.floor(sx), math.floor(sz)
        tx = self._smoothstep(sx - x0)
        tz = self._smoothstep(sz - z0)
        a = self._random_at(x0, z0)
        b = self._random_at(x0 + 1, z0)
        c = self._random_at(x0, z0 + 1)
        d = self._random_at(x0 + 1, z0 + 1)
        return (a + (b - a) * tx) + (
            (c + (d - c) * tx) - (a + (b - a) * tx)
        ) * tz

    def height_at(self, x, z):
        broad = self._noise(x, z, 32.0) * 4.0
        hills = self._noise(x + 1000, z - 1000, 15.0) * 2.0
        detail = self._noise(x - 2000, z + 2000, 7.0) * 0.6
        return max(2, min(12, round(6 + broad + hills + detail)))

    def generate_surface(self, world, size):
        # 先に全地点の高さを計算する。
        heights = {
            (x, z): self.height_at(x, z)
            for z in range(size)
            for x in range(size)
        }

        for z in range(size):
            for x in range(size):
                height = heights[(x, z)]

                # 最上面は草ブロック。
                world.place_block(x, height, z, 0)

                # 丘の側面から空洞が見えない範囲だけ土・石を生成する。
                # 地下全層は作らず、周囲で最も低い地表までに限定する。
                neighbor_heights = [
                    heights.get((x - 1, z), height),
                    heights.get((x + 1, z), height),
                    heights.get((x, z - 1), height),
                    heights.get((x, z + 1), height),
                ]
                visible_bottom = min(neighbor_heights)

                for y in range(height - 1, visible_bottom - 1, -1):
                    block_id = 1 if y >= height - 3 else 2
                    world.place_block(x, y, z, block_id)

        return heights
