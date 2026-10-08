"""wall/entity.py — стена: данные, геометрия, урон, трещины; менеджер стен."""
import math
import random

from engine import PX_PER_M, clamp, obb_segment_hit
from combat.armor import resolve_hit, Damageable
from .params import (
    WALL_PARAMS, WALL_ARMOR_K, WALL_HEIGHT_M, WALL_DENSITY_T_M3,
)

CRACK_COUNT_MIN, CRACK_COUNT_MAX = 8, 40

class Wall(Damageable):
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
    def volume_m3(self):
        return self.width_m * self.length_m * WALL_HEIGHT_M

    @property
    def mass_t(self):
        """Масса стены, т (объём × плотность бетона)."""
        return self.volume_m3 * WALL_DENSITY_T_M3

    @property
    def damage_fraction(self):
        """0 — целая, 1 — разрушена."""
        return 1.0 - clamp(self.hp / self.max_hp, 0.0, 1.0)

    @property
    def alive(self):
        return self.hp > 0.0

    @property
    def radius_px(self):
        """Радиус описанной окружности (для быстрых проверок «далеко/близко»)."""
        return math.hypot(self.half_w_px, self.half_l_px)

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

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        """Результат попадания (универсальный интерфейс цели). normal стене не нужна:
        броня одинакова со всех сторон."""
        return resolve_hit(penetration, self.armor_mm, cos_impact)

    # ---------- геометрия ----------
    def contains_point(self, x, y):
        u, v = self.to_local(x, y)
        return abs(u) <= self.half_w_px and abs(v) <= self.half_l_px

    def segment_hit(self, x0, y0, x1, y1):
        """Первое пересечение отрезка со стеной: (t, normal) или None."""
        return obb_segment_hit(self.obb(), x0, y0, x1, y1)

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

    def pick(self, x, y):
        """Верхняя стена под точкой мира или None."""
        for wall in reversed(self.items):
            if wall.contains_point(x, y):
                return wall
        return None

    def obbs_near(self, x, y, radius):
        """Прямоугольники только тех стен, что лежат в радиусе radius от точки (x, y)."""
        result = []
        for w in self.items:
            reach = radius + w.radius_px
            dx, dy = w.x - x, w.y - y
            if dx * dx + dy * dy <= reach * reach:
                result.append(w.obb())
        return result

    def raycast(self, x0, y0, x1, y1):
        """Ближайшая стена на отрезке: (wall, t, normal) или None."""
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        seg_r = math.hypot(x1 - x0, y1 - y0) / 2.0
        best = None
        for wall in self.items:
            reach = seg_r + wall.radius_px
            dx, dy = wall.x - mx, wall.y - my
            if dx * dx + dy * dy > reach * reach:
                continue  # стена заведомо далеко от отрезка
            res = wall.segment_hit(x0, y0, x1, y1)
            if res is not None and (best is None or res[0] < best[1]):
                best = (wall, res[0], res[1])
        return best

    def remove(self, wall):
        """Убрать конкретную стену (и снять выбор, если выбрана именно она)."""
        if wall in self.items:
            self.items.remove(wall)
        if self.selected is wall:
            self.selected = None

    def remove_dead(self):
        self.items = [w for w in self.items if w.alive]
        if self.selected is not None and self.selected not in self.items:
            self.selected = None