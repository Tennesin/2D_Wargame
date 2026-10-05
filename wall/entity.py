"""wall/entity.py — стена: данные, геометрия, урон, трещины; менеджер стен."""
import math
import random

from common import PX_PER_M, clamp
from .params import WALL_PARAMS, WALL_ARMOR_K

CRACK_COUNT_MIN, CRACK_COUNT_MAX = 8, 40


class Wall:
    """Осевой прямоугольник на земле. x, y — центр (мировые px). Ширина по X, длина по Y."""

    def __init__(self, x, y, hp, width_m, length_m):
        self.x = float(x)
        self.y = float(y)
        self.max_hp = float(hp)
        self.hp = float(hp)
        self.width_m = float(width_m)
        self.length_m = float(length_m)
        self._seed = random.randrange(1 << 30)     # от него зависит рисунок трещин
        self._crack_key = None
        self._crack_data = []

    @classmethod
    def default(cls, x, y):
        P = WALL_PARAMS
        return cls(x, y, P["wall_hp"].default, P["wall_width_m"].default, P["wall_length_m"].default)

    # ---------- размеры и броня ----------
    @property
    def half_w_px(self):
        return self.width_m * PX_PER_M / 2.0

    @property
    def half_l_px(self):
        return self.length_m * PX_PER_M / 2.0

    @property
    def thickness_m(self):
        """Толщина — меньшая из сторон."""
        return min(self.width_m, self.length_m)

    @property
    def armor_mm(self):
        return self.thickness_m * 1000.0 * WALL_ARMOR_K

    @property
    def damage_fraction(self):
        """0 — целая, 1 — разрушена."""
        return 1.0 - clamp(self.hp / self.max_hp, 0.0, 1.0)

    @property
    def alive(self):
        return self.hp > 0.0

    def rect(self):
        """(left, top, right, bottom) в мировых px."""
        hw, hl = self.half_w_px, self.half_l_px
        return (self.x - hw, self.y - hl, self.x + hw, self.y + hl)

    # ---------- изменения ----------
    def apply_params(self, hp, width_m, length_m):
        """Применить значения с панели. Доля повреждений сохраняется."""
        frac = self.hp / self.max_hp if self.max_hp > 0 else 1.0
        self.max_hp = float(hp)
        self.hp = self.max_hp * frac
        self.width_m = float(width_m)
        self.length_m = float(length_m)

    def take_hit(self, penetration, damage):
        """Попадание снаряда. Возвращает True, если пробил (стена получила урон)."""
        if penetration < self.armor_mm:
            return False
        self.hp = max(0.0, self.hp - damage)
        return True

    # ---------- геометрия ----------
    def contains_point(self, x, y):
        left, top, right, bottom = self.rect()
        return left <= x <= right and top <= y <= bottom

    def segment_hit(self, x0, y0, x1, y1):
        """Первая точка пересечения отрезка со стеной: доля пути t (0..1) или None."""
        left, top, right, bottom = self.rect()
        t0, t1 = 0.0, 1.0
        for p, q, lo, hi in ((x0, x1 - x0, left, right), (y0, y1 - y0, top, bottom)):
            if abs(q) < 1e-9:
                if p < lo or p > hi:
                    return None
            else:
                ta, tb = (lo - p) / q, (hi - p) / q
                if ta > tb:
                    ta, tb = tb, ta
                t0, t1 = max(t0, ta), min(t1, tb)
                if t0 > t1:
                    return None
        return t0

    # ---------- трещины (рисунок зависит от размеров и seed, не меняется между кадрами) ----------
    def cracks(self):
        """[(порог повреждений, [(dx, dy), ...]), ...] по возрастанию порога; координаты от центра, мировые px."""
        key = (self.width_m, self.length_m)
        if key != self._crack_key:
            self._crack_key = key
            self._crack_data = self._make_cracks()
        return self._crack_data

    def _make_cracks(self):
        rng = random.Random(self._seed)
        hw, hl = self.half_w_px, self.half_l_px
        count = int(clamp(8 + 3 * math.sqrt(self.width_m * self.length_m),
                          CRACK_COUNT_MIN, CRACK_COUNT_MAX))
        result = []
        for i in range(count):
            threshold = 0.05 + 0.85 * i / (count - 1)
            x = rng.uniform(-hw, hw)
            y = rng.uniform(-hl, hl)
            ang = rng.uniform(0.0, 2.0 * math.pi)
            pts = [(x, y)]
            for _ in range(rng.randint(4, 7)):
                ang += rng.uniform(-0.8, 0.8)
                step = rng.uniform(25.0, 70.0)
                x = clamp(x + math.cos(ang) * step, -hw, hw)
                y = clamp(y + math.sin(ang) * step, -hl, hl)
                pts.append((x, y))
            result.append((threshold, pts))
        return result


class WallManager:
    """Все стены на карте и выбранная."""

    def __init__(self):
        self.items = []
        self.selected = None

    def add(self, wall):
        self.items.append(wall)

    def rects(self):
        return [w.rect() for w in self.items]

    def pick(self, x, y):
        """Верхняя стена под точкой мира или None."""
        for wall in reversed(self.items):
            if wall.contains_point(x, y):
                return wall
        return None

    def raycast(self, x0, y0, x1, y1):
        """Ближайшая стена на отрезке: (wall, t) или None."""
        best = None
        for wall in self.items:
            t = wall.segment_hit(x0, y0, x1, y1)
            if t is not None and (best is None or t < best[1]):
                best = (wall, t)
        return best

    def remove_dead(self):
        self.items = [w for w in self.items if w.alive]
        if self.selected is not None and self.selected not in self.items:
            self.selected = None