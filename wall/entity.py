"""wall/entity.py — стена: данные, геометрия, урон, трещины; менеджер стен."""
import math
import random

from common import PX_PER_M, clamp
from .params import WALL_PARAMS, WALL_ARMOR_K, WALL_RICOCHET_ANGLE, PIERCE_SPREAD

RICOCHET_COS = math.cos(math.radians(WALL_RICOCHET_ANGLE))

def pierce_probability(penetration, armor_mm):
    """Шанс пробития 0..1. Окно ±PIERCE_SPREAD от пробития: слева 99%, справа 1%, в центре 50%."""
    if penetration <= 0.0:
        return 0.0
    x = (armor_mm - penetration) / (penetration * PIERCE_SPREAD)   # -1 .. +1 внутри окна
    if x <= -1.0:
        return 1.0
    if x >= 1.0:
        return 0.0
    return 0.5 - 0.49 * x

CRACK_COUNT_MIN, CRACK_COUNT_MAX = 8, 40

class Wall:
    """Осевой прямоугольник на земле. x, y — центр (мировые px). Ширина по X, длина по Y."""

    def __init__(self, x, y, hp, width_m, length_m, angle=0.0):
        self.x = float(x)
        self.y = float(y)
        self.max_hp = float(hp)
        self.hp = float(hp)
        self.width_m = float(width_m)
        self.length_m = float(length_m)
        self.angle = float(angle) % 360.0           # 0 = длинная сторона вдоль Y, по часовой
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

    # ---------- локальные координаты (u вправо вдоль ширины, v вниз вдоль длины, в px мира) ----------
    def to_world(self, u, v):
        rad = math.radians(self.angle)
        c, s = math.cos(rad), math.sin(rad)
        return self.x + u * c - v * s, self.y + u * s + v * c

    def to_local(self, x, y):
        rad = math.radians(self.angle)
        c, s = math.cos(rad), math.sin(rad)
        dx, dy = x - self.x, y - self.y
        return dx * c + dy * s, -dx * s + dy * c

    def obb(self):
        """Повёрнутый прямоугольник в формате столкновений: (x, y, half_w, half_l, angle)."""
        return (self.x, self.y, self.half_w_px, self.half_l_px, self.angle)

    # ---------- изменения ----------
    def apply_params(self, hp, width_m, length_m):
        """Применить значения с панели. Доля повреждений сохраняется."""
        frac = self.hp / self.max_hp if self.max_hp > 0 else 1.0
        self.max_hp = float(hp)
        self.hp = self.max_hp * frac
        self.width_m = float(width_m)
        self.length_m = float(length_m)

    def effective_armor_mm(self, cos_impact):
        """Броня с учётом наклона: чем косее удар, тем толще стена для снаряда."""
        return self.armor_mm / max(cos_impact, RICOCHET_COS)

    def is_ricochet(self, cos_impact):
        """Рикошетит ли снаряд при таком косинусе угла к нормали."""
        return cos_impact < RICOCHET_COS

    def pierce_check(self, penetration, cos_impact=1.0):
        """(приведённая броня, шанс 0..1). При рикошете: (None, 0.0)."""
        if cos_impact < RICOCHET_COS:
            return None, 0.0
        eff = self.effective_armor_mm(cos_impact)
        return eff, pierce_probability(penetration, eff)

    def take_hit(self, penetration, damage, cos_impact=1.0):
        """Попадание снаряда. cos_impact: косинус угла между траекторией и нормалью к грани
        (1 = прямой удар). Пробитие определяется броском по шансу. Возвращает True, если пробил."""
        _, chance = self.pierce_check(penetration, cos_impact)
        if chance <= 0.0 or random.random() >= chance:
            return False
        self.hp = max(0.0, self.hp - damage)
        return True

    # ---------- геометрия ----------
    def contains_point(self, x, y):
        u, v = self.to_local(x, y)
        return abs(u) <= self.half_w_px and abs(v) <= self.half_l_px

    def segment_hit(self, x0, y0, x1, y1):
        """Первое пересечение отрезка со стеной: (t, normal) или None.
        t — доля пути (0..1); normal — единичная нормаль грани, в которую вошли (мировые координаты),
        либо None, если отрезок начинается внутри стены."""
        u0, v0 = self.to_local(x0, y0)
        u1, v1 = self.to_local(x1, y1)
        t0, t1 = 0.0, 1.0
        normal_local = None
        for axis, p, q, half in ((0, u0, u1 - u0, self.half_w_px),
                                 (1, v0, v1 - v0, self.half_l_px)):
            if abs(q) < 1e-9:
                if abs(p) > half:
                    return None
                continue
            ta, tb = (-half - p) / q, (half - p) / q
            sign = -1.0 if q > 0 else 1.0       # грань, через которую входим, смотрит против движения
            if ta > tb:
                ta, tb = tb, ta
            if ta > t0:
                t0 = ta
                normal_local = (sign, 0.0) if axis == 0 else (0.0, sign)
            t1 = min(t1, tb)
            if t0 > t1:
                return None

        if normal_local is None:
            return t0, None
        rad = math.radians(self.angle)
        c, s = math.cos(rad), math.sin(rad)
        nu, nv = normal_local
        return t0, (nu * c - nv * s, nu * s + nv * c)

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

    def obbs(self):
        return [w.obb() for w in self.items]

    def pick(self, x, y):
        """Верхняя стена под точкой мира или None."""
        for wall in reversed(self.items):
            if wall.contains_point(x, y):
                return wall
        return None

    def raycast(self, x0, y0, x1, y1):
        """Ближайшая стена на отрезке: (wall, t, normal) или None."""
        best = None
        for wall in self.items:
            res = wall.segment_hit(x0, y0, x1, y1)
            if res is not None and (best is None or res[0] < best[1]):
                best = (wall, res[0], res[1])
        return best

    def remove_dead(self):
        self.items = [w for w in self.items if w.alive]
        if self.selected is not None and self.selected not in self.items:
            self.selected = None