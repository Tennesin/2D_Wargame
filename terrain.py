"""terrain.py — естественные препятствия: камни, вода, грязь.
Мир делится на большие ячейки; в каждой по seed создаётся набор «пятен» — многоугольников
разной формы и размера. У пятна есть вид местности: непроходимый (solid) или замедляющий (speed_k < 1).
Камни ещё и останавливают снаряды (blocks_shells) и имеют массу (заготовка для тарана).
Здесь нет pygame: рисует terrain_render.py."""
import math
import random
from dataclasses import dataclass

from armor import resolve_hit
from common import PX_PER_M, clamp, obb_hits_convex, LRUCache
from core import hash_int

TAU = 2.0 * math.pi

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
FEATURE_CELL = 3000.0        # размер ячейки генерации, px мира (30 м)
MAX_PATCH_R = 2600.0         # никакое пятно не выходит за этот радиус от центра (нужно для поиска соседей)
SPAWN_CLEAR = 600.0          # вокруг точки (0, 0) пятен нет, px
CELL_CACHE_LIMIT = 600

# --- озёра: три вложенные зоны ---
LAKE_CHANCE = 0.28           # вероятность озера в ячейке
LAKE_RADIUS = (900.0, 2000.0)
MID_SCALE = 0.68             # зона «вода» (брод): доля размера мелководья
DEEP_SCALE = 0.38            # глубокая часть (непроходима): доля размера мелководья

# --- грязь ---
MUD_CHANCE = 0.35
MUD_RADIUS = (500.0, 1400.0)

# --- камни ---
ROCK_CELL_CHANCE = 0.55      # вероятность, что в ячейке вообще есть камни
ROCKS_PER_CELL = (1, 3)      # сколько камней в такой ячейке (min, max)
ROCK_SMALL = (80.0, 200.0)   # радиус, px (0,8–2 м)
ROCK_MEDIUM = (250.0, 450.0)
ROCK_BIG = (600.0, 1000.0)   # скальные гряды
ROCK_MEDIUM_P = 0.23         # доля средних
ROCK_BIG_P = 0.07            # доля больших

# --- множители скорости ---
SHALLOWS_K = 0.60            # мелководье: замедление 40%
MID_WATER_K = 0.40           # вода средней глубины: замедление 60%
MUD_K = 0.40

# --- масса камней ---
ROCK_DENSITY = 2.7           # гранит, т/м³
ROCK_SHAPE_K = 0.65          # камень — не коробка, а «купол»: доля от площадь × высота
ROCK_H_BASE = 0.4            # высота = ROCK_H_BASE + ROCK_H_K × (радиус круга той же площади, м)
ROCK_H_K = 0.45
ROCK_H_MIN, ROCK_H_MAX = 0.5, 4.0
ROCK_ARMOR_MM = 3000.0       # броня камня: практически непробиваем


@dataclass(frozen=True)
class TerrainKind:
    name: str
    speed_k: float                 # множитель скорости: 1.0 как трава, 0.0 — нельзя
    solid: bool                    # блокирует корпус
    layer: int                     # порядок рисования: меньше — раньше
    density: float = 0.0           # т/м³; 0 — масса не считается (вода, грязь)
    armor_mm: float = 0.0          # броня для снарядов (имеет смысл, если blocks_shells)
    blocks_shells: bool = False    # останавливает снаряды


# Чтобы добавить новый вид, достаточно объявить его здесь, добавить строку в _generate
# и цвета в terrain_render.py.
SHALLOWS = TerrainKind("Мелководье", SHALLOWS_K, False, 0)
MUD = TerrainKind("Грязь", MUD_K, False, 1)
MID_WATER = TerrainKind("Вода", MID_WATER_K, False, 2)
DEEP_WATER = TerrainKind("Глубокая вода", 0.0, True, 3)
ROCK = TerrainKind("Камень", 0.0, True, 4,
                   density=ROCK_DENSITY, armor_mm=ROCK_ARMOR_MM, blocks_shells=True)


# ==========================================
# 2. ПЯТНО
# ==========================================
def _polygon_area(pts):
    """Площадь многоугольника (формула Гаусса), px²."""
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


class Patch:
    """Одно препятствие: звёздчатый многоугольник вокруг центра (мировые px)."""

    def __init__(self, kind, x, y, pts):
        self.kind = kind
        self.x, self.y = x, y
        self.pts = pts
        self.r_max = max(math.hypot(px - x, py - y) for px, py in pts)
        self.area_m2 = _polygon_area(pts) / (PX_PER_M * PX_PER_M)
        n = len(pts)
        # треугольники для столкновений нужны только твёрдым пятнам
        self.tris = ([((x, y), pts[i], pts[(i + 1) % n]) for i in range(n)]
                     if kind.solid else ())

    # ---------- вес (заготовка для тарана) ----------
    @property
    def height_m(self):
        if self.kind.density <= 0.0:
            return 0.0
        r_eq = math.sqrt(self.area_m2 / math.pi)
        return clamp(ROCK_H_BASE + ROCK_H_K * r_eq, ROCK_H_MIN, ROCK_H_MAX)

    @property
    def volume_m3(self):
        return self.area_m2 * self.height_m * ROCK_SHAPE_K

    @property
    def mass_t(self):
        """Масса, т (0 для воды и грязи)."""
        return self.volume_m3 * self.kind.density

    # ---------- геометрия ----------
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

    def segment_hit(self, x0, y0, x1, y1):
        """Первое пересечение отрезка с границей: (t, normal) или None.
        normal — наружная нормаль ребра (None, если отрезок начинается внутри пятна)."""
        if self.contains(x0, y0):
            return 0.0, None
        rx, ry = x1 - x0, y1 - y0
        best_t, best_n = None, None
        pts = self.pts
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            sx, sy = bx - ax, by - ay
            denom = rx * sy - ry * sx
            if abs(denom) < 1e-9:
                continue
            qx, qy = ax - x0, ay - y0
            t = (qx * sy - qy * sx) / denom
            u = (qx * ry - qy * rx) / denom
            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0 and (best_t is None or t < best_t):
                ln = math.hypot(sx, sy)
                if ln < 1e-9:
                    continue
                nx, ny = sy / ln, -sx / ln
                if nx * ((ax + bx) / 2.0 - self.x) + ny * ((ay + by) / 2.0 - self.y) < 0.0:
                    nx, ny = -nx, -ny                    # нормаль должна смотреть наружу
                best_t, best_n = t, (nx, ny)
        return None if best_t is None else (best_t, best_n)

    # ---------- интерфейс цели для снарядов ----------
    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.kind.armor_mm, cos_impact)

    def take_hit(self, penetration, damage, cos_impact=1.0, normal=None):
        """Камень неразрушаем: урон не наносится."""
        return 0.0


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


def _scaled(patch, k):
    """Контур пятна, уменьшенный к его центру в k раз."""
    return [(patch.x + (px - patch.x) * k, patch.y + (py - patch.y) * k) for px, py in patch.pts]


# ==========================================
# 3. КАРТА ПРЕПЯТСТВИЙ
# ==========================================
class TerrainMap:
    """Всё о препятствиях: что где лежит, что под точкой, мешает ли прямоугольник, куда попал снаряд."""

    def __init__(self, seed):
        self.seed = seed
        self._cells = LRUCache(CELL_CACHE_LIMIT)  # (ix, iy) -> [Patch, ...]

    # ---------- генерация ----------
    def _generate(self, ix, iy):
        rng = random.Random(hash_int(ix, iy, self.seed + 4242))
        ox, oy = ix * FEATURE_CELL, iy * FEATURE_CELL
        patches = []
        lakes = []

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
                lakes.append(shore)
                patches.append(shore)
                patches.append(Patch(MID_WATER, shore.x, shore.y, _scaled(shore, MID_SCALE)))
                patches.append(Patch(DEEP_WATER, shore.x, shore.y, _scaled(shore, DEEP_SCALE)))

        if rng.random() < MUD_CHANCE:
            mud = place(MUD, rng.uniform(*MUD_RADIUS), 16, rng.uniform(1.0, 1.6), 0.28, 0.06)
            if mud is not None:
                patches.append(mud)

        if rng.random() < ROCK_CELL_CHANCE:
            for _ in range(rng.randint(*ROCKS_PER_CELL)):
                roll = rng.random()
                if roll < ROCK_BIG_P:
                    radius = rng.uniform(*ROCK_BIG)
                elif roll < ROCK_BIG_P + ROCK_MEDIUM_P:
                    radius = rng.uniform(*ROCK_MEDIUM)
                else:
                    radius = rng.uniform(*ROCK_SMALL)
                rock = place(ROCK, radius, rng.randint(7, 11), rng.uniform(1.0, 1.7), 0.15, 0.20)
                if rock is None:
                    continue
                if any(lake.contains(rock.x, rock.y) for lake in lakes):   # камней посреди озера не бывает
                    continue
                patches.append(rock)
        return patches

    def _cell(self, ix, iy):
        return self._cells.get_or_build((ix, iy), lambda: self._generate(ix, iy))

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

    def raycast(self, x0, y0, x1, y1):
        """Ближайшее пятно, останавливающее снаряды, на отрезке: (patch, t, normal) или None.
        Тот же формат, что у WallManager.raycast, поэтому карта подключается в TargetSet как есть."""
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        radius = math.hypot(x1 - x0, y1 - y0) / 2.0
        best = None
        for p in self._near(mx, my, radius):
            if not p.kind.blocks_shells:
                continue
            res = p.segment_hit(x0, y0, x1, y1)
            if res is not None and (best is None or res[0] < best[1]):
                best = (p, res[0], res[1])
        return best