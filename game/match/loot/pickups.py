"""game/match/loot/pickups.py — предметы на земле. Сейчас только обломки; останки улучшений добавятся рядом."""
import math

from engine import heading_vector, PX_PER_M
from .params import WRECK_LIFE_S, WRECK_HOLD_S, UPGRADE_LIFE_S, WRECK_ZONE_MARGIN_M

# обход прямоугольника по кругу: (доля ширины, доля длины)
_RING = ((-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0))
_JITTER = 0.14               # разброс вершин силуэта

class Wreck:
    """Обломки уничтоженной техники. Координаты фигур хранятся смещениями от центра, мировые px."""

    def __init__(self, x, y, half_w, half_l, angle, key, color, rng):
        self.x, self.y = x, y
        self.key = key                  # ключ архетипа погибшей техники
        self.color = color              # цвет архетипа (рисуется кольцом на «башне»)
        self.life = WRECK_LIFE_S        # сколько секунд осталось
        self.hold = 0.0                 # сколько секунд игрок уже стоит на обломках
        self.taken = False              # подобраны: убрать

        fx, fy = heading_vector(angle)
        rx, ry = -fy, fx

        def offset(u, v, k=1.0):
            a, b = u * half_w * k, v * half_l * k
            return rx * a + fx * b, ry * a + fy * b

        self.body = [offset(u, v, 1.0 + rng.uniform(-_JITTER, _JITTER)) for u, v in _RING]
        sx, sy = rng.uniform(-0.25, 0.25), rng.uniform(-0.30, 0.30)
        self.scorch = [offset(u * 0.6 + sx, v * 0.6 + sy) for u, v in _RING]
        self.turret_pos = offset(rng.uniform(-0.25, 0.25), rng.uniform(-0.20, 0.35))
        self.turret_r = half_w * 0.45
        self.extent = max(math.hypot(px, py) for px, py in self.body) + 4.0    # радиус описанного круга
        self.zone = self.extent + WRECK_ZONE_MARGIN_M * PX_PER_M     # радиус зоны сбора, px мира

    @classmethod
    def from_tank(cls, tank, key, color, rng):
        x, y, half_w, half_l, angle = tank.hull_obb()      # центр корпуса, а не ось орудия
        return cls(x, y, half_w, half_l, angle, key, color, rng)

    @property
    def hold_frac(self):
        return min(1.0, self.hold / WRECK_HOLD_S)

class UpgradeRemains:
    """Останки улучшения. Лежат UPGRADE_LIFE_S секунд; игрок может взять их или отказаться."""

    def __init__(self, x, y, key, color):
        self.x, self.y = x, y
        self.key = key                  # ключ улучшения (= ключ архетипа)
        self.color = color              # цвет архетипа
        self.life = UPGRADE_LIFE_S      # сколько секунд осталось
        self.gone = False               # взяты или отклонены: убрать