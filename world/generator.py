"""world/generator.py — процедурный мир: трава и декор."""
import random
from dataclasses import dataclass
from typing import List

from engine import clamp, lerp_color, hash_int, hash_float, value_noise

# ==========================================
# НАСТРОЙКИ МИРА
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

# ==========================================
# 2. ПРОЦЕДУРНЫЙ МИР
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