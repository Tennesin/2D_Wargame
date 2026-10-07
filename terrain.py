"""terrain.py — естественные препятствия: камни, вода, грязь.
Мир делится на большие ячейки; в каждой по seed создаётся набор «пятен» — многоугольников
разной формы и размера. У пятна есть вид местности: непроходимый (solid) или замедляющий (speed_k < 1).
Здесь нет pygame: рисует terrain_render.py."""
import math
import random
from collections import OrderedDict
from dataclasses import dataclass

from common import obb_hits_convex
from core import hash_int

TAU = 2.0 * math.pi

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
FEATURE_CELL = 3000.0        # размер ячейки генерации, px мира (30 м)
MAX_PATCH_R = 2600.0         # никакое пятно не выходит за этот радиус от центра (нужно для поиска соседей)
SPAWN_CLEAR = 600.0          # вокруг точки (0, 0) пятен нет, px
CELL_CACHE_LIMIT = 600

LAKE_CHANCE = 0.12           # вероятность озера в ячейке
LAKE_RADIUS = (900.0, 2000.0)
DEEP_SCALE = 0.60            # глубокая часть озера: доля размера мелководья

MUD_CHANCE = 0.14
MUD_RADIUS = (500.0, 1400.0)

ROCKS_PER_CELL = (0, 6)      # сколько камней на ячейку (min, max)
ROCK_SMALL = (80.0, 200.0)   # радиус, px (0,8–2 м)
ROCK_MEDIUM = (250.0, 450.0)
ROCK_BIG = (600.0, 1000.0)   # скальные гряды
ROCK_MEDIUM_P = 0.23         # доля средних
ROCK_BIG_P = 0.07            # доля больших


@dataclass(frozen=True)
class TerrainKind:
    name: str
    speed_k: float           # множитель скорости: 1.0 как трава, 0.0 — нельзя
    solid: bool              # блокирует корпус
    layer: int               # порядок рисования: меньше — раньше


# Чтобы добавить новый вид, достаточно объявить его здесь, добавить строку в _generate
# и цвета в terrain_render.py.
SHALLOWS = TerrainKind("Мелководье", 0.30, False, 0)
MUD = TerrainKind("Грязь", 0.40, False, 1)
DEEP_WATER = TerrainKind("Глубокая вода", 0.0, True, 2)
ROCK = TerrainKind("Камень", 0.0, True, 3)


# ==========================================
# 2. ПЯТНО
# ==========================================
class Patch:
    """Одно препятствие: звёздчатый многоугольник вокруг центра (мировые px)."""

    def __init__(self, kind, x, y, pts):
        self.kind = kind
        self.x, self.y = x, y
        self.pts = pts
        self.r_max = max(math.hypot(px - x, py - y) for px, py in pts)
        n = len(pts)
        # треугольники для столкновений нужны только твёрдым пятнам
        self.tris = ([((x, y), pts[i], pts[(i + 1) % n]) for i in range(n)]
                     if kind.solid else ())

    def contains(self, x, y):
        """Лежит ли точка внутри многоугольника."""
        dx, dy = x - self.x, y - self.y
        if dx * dx + dy * dy > self.r_max * self.r_max:
            return False
        inside = False
        pts = self.pts
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside


def _make_pts(rng, cx, cy, radius, n, stretch=1.0, rough=0.2, jitter=0.1):
    """Вершины неровной фигуры: радиус меняется плавно (rough) и случайно (jitter),
    затем фигура растягивается в stretch раз и поворачивается."""
    rot = rng.uniform(0.0, math.pi)
    cr, sr = math.cos(rot), math.sin(rot)
    p1, p2 = rng.uniform(0.0, TAU), rng.uniform(0.0, TAU)
    pts = []
    for i in range(n):
        a = TAU * i / n
        k = (1.0 + rough * math.sin(2.0 * a + p1) + 0.6 * rough * math.sin(3.0 * a + p2)
             + rng.uniform(-jitter, jitter))
        k = max(0.4, k)
        lx = math.cos(a) * radius * k * stretch
        ly = math.sin(a) * radius * k / stretch
        pts.append((cx + lx * cr - ly * sr, cy + lx * sr + ly * cr))

    rmax = max(math.hypot(px - cx, py - cy) for px, py in pts)
    if rmax > MAX_PATCH_R:                       # не даём фигуре выйти за допустимый радиус
        s = MAX_PATCH_R / rmax
        pts = [(cx + (px - cx) * s, cy + (py - cy) * s) for px, py in pts]
    return pts


# ==========================================
# 3. КАРТА ПРЕПЯТСТВИЙ
# ==========================================
class TerrainMap:
    """Всё о препятствиях: что где лежит, что под точкой, мешает ли прямоугольник."""

    def __init__(self, seed):
        self.seed = seed
        self._cells = OrderedDict()              # (ix, iy) -> [Patch, ...]

    # ---------- генерация ----------
    def _generate(self, ix, iy):
        rng = random.Random(hash_int(ix, iy, self.seed + 4242))
        ox, oy = ix * FEATURE_CELL, iy * FEATURE_CELL
        patches = []

        def place(kind, radius, n, stretch, rough, jitter):
            x = ox + rng.uniform(0.0, FEATURE_CELL)
            y = oy + rng.uniform(0.0, FEATURE_CELL)
            pts = _make_pts(rng, x, y, radius, n, stretch, rough, jitter)
            patch = Patch(kind, x, y, pts)
            if math.hypot(x, y) - patch.r_max < SPAWN_CLEAR:     # стартовую площадку не трогаем
                return None
            return patch

        if rng.random() < LAKE_CHANCE:
            shore = place(SHALLOWS, rng.uniform(*LAKE_RADIUS), 22, rng.uniform(1.0, 1.5), 0.22, 0.04)
            if shore is not None:
                patches.append(shore)
                deep = [(shore.x + (px - shore.x) * DEEP_SCALE,
                         shore.y + (py - shore.y) * DEEP_SCALE) for px, py in shore.pts]
                patches.append(Patch(DEEP_WATER, shore.x, shore.y, deep))

        if rng.random() < MUD_CHANCE:
            mud = place(MUD, rng.uniform(*MUD_RADIUS), 16, rng.uniform(1.0, 1.6), 0.28, 0.06)
            if mud is not None:
                patches.append(mud)

        for _ in range(rng.randint(*ROCKS_PER_CELL)):
            roll = rng.random()
            if roll < ROCK_BIG_P:
                radius = rng.uniform(*ROCK_BIG)
            elif roll < ROCK_BIG_P + ROCK_MEDIUM_P:
                radius = rng.uniform(*ROCK_MEDIUM)
            else:
                radius = rng.uniform(*ROCK_SMALL)
            rock = place(ROCK, radius, rng.randint(7, 11), rng.uniform(1.0, 1.7), 0.15, 0.20)
            if rock is not None:
                patches.append(rock)
        return patches

    def _cell(self, ix, iy):
        key = (ix, iy)
        cell = self._cells.get(key)
        if cell is None:
            cell = self._generate(ix, iy)
            self._cells[key] = cell
            while len(self._cells) > CELL_CACHE_LIMIT:
                self._cells.popitem(last=False)
        return cell

    # ---------- поиск ----------
    def _near(self, x, y, radius):
        """Пятна, чей круг (центр, r_max) пересекается с кругом (x, y, radius)."""
        reach = radius + MAX_PATCH_R
        ix0 = math.floor((x - reach) / FEATURE_CELL)
        ix1 = math.floor((x + reach) / FEATURE_CELL)
        iy0 = math.floor((y - reach) / FEATURE_CELL)
        iy1 = math.floor((y + reach) / FEATURE_CELL)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                for p in self._cell(ix, iy):
                    dx, dy = p.x - x, p.y - y
                    lim = p.r_max + radius
                    if dx * dx + dy * dy <= lim * lim:
                        yield p

    def patches_in_rect(self, x0, y0, x1, y1):
        """Пятна, которые могут попасть в прямоугольник мира (для рисования), по порядку слоёв."""
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        radius = math.hypot(x1 - x0, y1 - y0) / 2.0
        return sorted(self._near(mx, my, radius), key=lambda p: p.kind.layer)

    def kind_at(self, x, y):
        """Вид местности под точкой (самый «тяжёлый» из перекрывающихся) или None — обычная трава."""
        best = None
        for p in self._near(x, y, 0.0):
            if p.contains(x, y) and (best is None or p.kind.speed_k < best.speed_k):
                best = p.kind
        return best

    def speed_factor(self, x, y):
        kind = self.kind_at(x, y)
        return 1.0 if kind is None else kind.speed_k

    def blocks_obb(self, obb):
        """Задевает ли повёрнутый прямоугольник (x, y, half_w, half_l, angle) твёрдое пятно."""
        cx, cy, hw, hl, ang = obb
        for p in self._near(cx, cy, math.hypot(hw, hl)):
            if not p.kind.solid:
                continue
            for tri in p.tris:
                if obb_hits_convex(cx, cy, hw, hl, ang, tri):
                    return True
        return False