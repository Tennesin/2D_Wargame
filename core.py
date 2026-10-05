"""core.py — мир: шум и хеши, камера, процедурный генератор земли и декора.
Здесь нет ни pygame-отрисовки, ни чтения клавиатуры."""
import math
import random
from dataclasses import dataclass
from typing import List

from common import clamp, lerp, lerp_color

# ==========================================
# 1. НАСТРОЙКИ МИРА
# ==========================================
CHUNK_SIZE = 512          # размер чанка (px)
CELL_SIZE = 16            # размер клетки земли (px); CHUNK_SIZE должен делиться на него
DECOR_ATTEMPTS = 90       # сколько попыток поставить декор на чанк
DECOR_MARGIN = 20         # отступ от края чанка, чтобы рисунки не обрезались

DRY_GRASS = (158, 184, 96)    # светлая сухая трава
LUSH_GRASS = (46, 112, 52)    # тёмная густая трава
FLOWER_COLORS = [
    (238, 238, 246),  # белый
    (242, 202, 60),   # жёлтый
    (222, 72, 92),    # красный
    (172, 112, 204),  # сиреневый
    (242, 142, 60),   # оранжевый
]
ZOOM_LEVELS = [round(0.10 * 6 ** (i / 20), 4) for i in range(21)]   # 0.10 … 0.60, шаг ≈ 9 %
DEFAULT_ZOOM_LEVEL = 5                                               # ≈ 0.157: танк 7 м ≈ 110 px

# ==========================================
# 2. МАТЕМАТИЧЕСКИЕ ПОМОЩНИКИ
# ==========================================

def hash_int(ix, iy, seed):
    """Детерминированный целочисленный хеш трёх чисел (32 бита)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 144269504) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def hash_float(ix, iy, seed):
    """То же, но результат в диапазоне 0..1."""
    return hash_int(ix, iy, seed) / 4294967295.0


def value_noise(x, y, seed):
    """Плавный шум 0..1: хеши в углах клетки, сглаженная интерполяция."""
    x0 = math.floor(x)
    y0 = math.floor(y)
    fx = x - x0
    fy = y - y0
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    x0 = int(x0)
    y0 = int(y0)
    v00 = hash_float(x0, y0, seed)
    v10 = hash_float(x0 + 1, y0, seed)
    v01 = hash_float(x0, y0 + 1, seed)
    v11 = hash_float(x0 + 1, y0 + 1, seed)
    return lerp(lerp(v00, v10, fx), lerp(v01, v11, fx), fy)

# ==========================================
# 3. КАМЕРА
# ==========================================
class Camera:
    """Камера: центр в мировых координатах + зум. Мир: 100 px = 1 м; на экране 1 м = 100 * zoom px."""

    def __init__(self, view_w=800, view_h=600):
        self.x = 0.0
        self.y = 0.0
        self.view_w = view_w
        self.view_h = view_h
        self.zoom_level = DEFAULT_ZOOM_LEVEL

    @property
    def zoom(self):
        return ZOOM_LEVELS[self.zoom_level]

    def zoom_by(self, steps):
        """Сдвинуть уровень зума: steps > 0 — приблизить, < 0 — отдалить."""
        self.zoom_level = int(clamp(self.zoom_level + steps, 0, len(ZOOM_LEVELS) - 1))

    def resize(self, view_w, view_h):
        self.view_w = view_w
        self.view_h = view_h

    def center_on(self, x, y):
        self.x = x
        self.y = y

    def origin_px(self):
        """Сдвиг мира в ЭКРАННЫХ пикселях (целые числа, чтобы земля не дрожала)."""
        z = self.zoom
        return round(self.x * z) - self.view_w // 2, round(self.y * z) - self.view_h // 2

    def world_to_screen(self, wx, wy):
        z = self.zoom
        left, top = self.origin_px()
        return wx * z - left, wy * z - top

    def screen_to_world(self, sx, sy):
        z = self.zoom
        left, top = self.origin_px()
        return (sx + left) / z, (sy + top) / z

# ==========================================
# 5. ПРОЦЕДУРНЫЙ МИР
# ==========================================
@dataclass
class Decoration:
    kind: str        # "flower", "stone", "bush", "tuft"
    x: float         # координаты ВНУТРИ чанка
    y: float
    size: float
    color: tuple
    variant: int     # число для мелких различий внешнего вида


class WorldGenerator:
    """Данные о мире: какая тут трава и какой декор. Рисует не он, а Renderer."""

    def __init__(self, seed):
        self.seed = seed

    def grass_at(self, wx, wy):
        """Густота травы в точке мира: 0 (сухо) .. 1 (густо)."""
        n = (0.60 * value_noise(wx / 700.0, wy / 700.0, self.seed)
             + 0.28 * value_noise(wx / 220.0, wy / 220.0, self.seed + 101)
             + 0.12 * value_noise(wx / 70.0, wy / 70.0, self.seed + 202))
        # шум кучкуется около 0.5, растягиваем, чтобы были и светлые, и тёмные области
        return clamp((n - 0.5) * 2.0 + 0.5, 0.0, 1.0)

    @staticmethod
    def grass_color(g):
        return lerp_color(DRY_GRASS, LUSH_GRASS, g)

    def ground_color(self, cell_x, cell_y, cell_size=CELL_SIZE):
        """Цвет клетки земли (индексы клеток, не пиксели). cell_size больше обычного — для дальнего зума."""
        g = self.grass_at((cell_x + 0.5) * cell_size, (cell_y + 0.5) * cell_size)
        base = self.grass_color(g)
        jitter = int((hash_float(cell_x, cell_y, self.seed + 7) - 0.5) * 12)
        return tuple(clamp(c + jitter, 0, 255) for c in base)

    def chunk_decorations(self, cx, cy) -> List[Decoration]:
        """Декор одного чанка. Одинаков при каждом вызове для одних и тех же cx, cy."""
        rng = random.Random(hash_int(cx, cy, self.seed + 999))
        origin_x = cx * CHUNK_SIZE
        origin_y = cy * CHUNK_SIZE
        low, high = DECOR_MARGIN, CHUNK_SIZE - DECOR_MARGIN
        result: List[Decoration] = []

        for _ in range(DECOR_ATTEMPTS):
            x = rng.uniform(low, high)
            y = rng.uniform(low, high)
            g = self.grass_at(origin_x + x, origin_y + y)
            roll = rng.random()

            stone_p = 0.04 + 0.10 * (1.0 - g)   # на сухой земле камней больше
            flower_p = 0.30 * g * g             # цветы любят густую траву
            bush_p = 0.06 * g * g
            tuft_p = 0.30

            if roll < stone_p:
                v = rng.randint(95, 150)
                result.append(Decoration("stone", x, y, rng.uniform(5, 12),
                                         (v, v, v + 6), rng.randint(0, 99)))
            elif roll < stone_p + flower_p:
                color = rng.choice(FLOWER_COLORS)
                for _k in range(rng.randint(2, 5)):      # цветы растут группкой
                    fx = clamp(x + rng.uniform(-16, 16), low, high)
                    fy = clamp(y + rng.uniform(-16, 16), low, high)
                    result.append(Decoration("flower", fx, fy, rng.choice((3, 4)),
                                             color, rng.randint(0, 99)))
            elif roll < stone_p + flower_p + bush_p:
                s = rng.randint(0, 25)
                result.append(Decoration("bush", x, y, rng.uniform(8, 13),
                                         (28 + s, 80 + s, 38 + s), rng.randint(0, 99)))
            elif roll < stone_p + flower_p + bush_p + tuft_p:
                dark = lerp_color(self.grass_color(g), (10, 40, 15), 0.45)
                result.append(Decoration("tuft", x, y, rng.uniform(4, 7),
                                         dark, rng.randint(0, 99)))

        result.sort(key=lambda d: d.y)   # нижние рисуются поверх верхних
        return result