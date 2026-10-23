"""world/generator.py — процедурный мир: густота и цвет травы. Декора (цветов, кустов, камешков) нет."""
import math

from engine import clamp, lerp_color, hash_float, value_noise, SEED_SALT

CHUNK_SIZE = 512          # размер чанка (px)

DRY_GRASS = (158, 184, 96)    # светлая сухая трава
LUSH_GRASS = (46, 112, 52)    # тёмная густая трава

PALETTE_SIZE = 256
GRASS_PALETTE = [lerp_color(DRY_GRASS, LUSH_GRASS, i / (PALETTE_SIZE - 1)) for i in range(PALETTE_SIZE)]

# слои шума: (период в px мира, добавка к сиду, вес)
_LAYERS = (
    (700.0, 0, 0.60),
    (220.0, SEED_SALT["grass_mid"], 0.28),
    (70.0, SEED_SALT["grass_fine"], 0.12),
)

class WorldGenerator:
    """Данные о мире: какая тут трава. Рисует не он, а GroundRenderer."""

    def __init__(self, seed):
        self.seed = seed

    def grass_at(self, wx, wy):
        """Густота травы в точке мира: 0 (сухо) .. 1 (густо)."""
        n = sum(w * value_noise(wx / period, wy / period, self.seed + salt)
                for period, salt, w in _LAYERS)
        # шум кучкуется около 0.5, растягиваем, чтобы были и светлые, и тёмные области
        return clamp((n - 0.5) * 2.0 + 0.5, 0.0, 1.0)

    @staticmethod
    def grass_color(g):
        return lerp_color(DRY_GRASS, LUSH_GRASS, g)

    @staticmethod
    def _lattice(coord, period):
        """Клетка шума и сглаженная дробная часть для одной координаты."""
        u = coord / period
        i = math.floor(u)
        f = u - i
        return i, f * f * (3.0 - 2.0 * f)

    def grass_grid(self, x0, y0, step, count):
        """Густота травы в узлах сетки count x count: узел (i, j) лежит в точке (x0 + i*step, y0 + j*step).
        Значения те же, что у grass_at, но хеши решётки шума считаются один раз на слой, а не на каждую точку.
        Возвращает список строк: grid[j][i]."""
        total = [[0.0] * count for _ in range(count)]
        for period, salt, weight in _LAYERS:
            seed = self.seed + salt
            cols = [self._lattice(x0 + i * step, period) for i in range(count)]
            rows = [self._lattice(y0 + j * step, period) for j in range(count)]
            ix_min, ix_max = cols[0][0], cols[-1][0]
            lines = {}                                   # iy -> хеши вдоль оси X для этой строки решётки

            def line(iy):
                values = lines.get(iy)
                if values is None:
                    values = lines[iy] = [hash_float(ix, iy, seed) for ix in range(ix_min, ix_max + 2)]
                return values

            for j in range(count):
                iy, fy = rows[j]
                top, bot = line(iy), line(iy + 1)
                out = total[j]
                for i in range(count):
                    ix, fx = cols[i]
                    k = ix - ix_min
                    a, c = top[k], bot[k]
                    t = a + (top[k + 1] - a) * fx
                    b = c + (bot[k + 1] - c) * fx
                    out[i] += weight * (t + (b - t) * fy)

