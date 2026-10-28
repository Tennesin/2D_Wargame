"""world/terrain.py — естественные препятствия: камни (многоугольники) и вода/грязь (сетка ландшафта).
Здесь нет pygame: рисует terrain_render.py. Генерацию по сиду делает natural.py."""
import math
from dataclasses import dataclass

from combat import resolve_hit
from engine import (
    PX_PER_M, clamp, obb_hits_convex, obb_hits_obb, TAU, obb_outside_rect, TargetType, fmt_num
)
from .landscape import CELL_PX, L_DEEP
from .mapdata import MAX_ROCK_R_PX
from .rock_physics import RockMover

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================

FEATURE_CELL = 3000.0        # размер ячейки генерации и поиска камней, px мира (30 м)
MAX_PATCH_R = MAX_ROCK_R_PX  # никакое пятно не выходит за этот радиус от центра (нужно для поиска соседей)
SPAWN_CLEAR = 1400.0         # вокруг точки (0, 0) пятен нет, px

# --- озёра: три вложенные зоны ---
LAKE_CHANCE = 0.28
LAKE_RADIUS = (900.0, 2000.0)
MID_SCALE = 0.68             # зона «вода» (брод): доля размера мелководья
DEEP_SCALE = 0.38            # глубокая часть (непроходима): доля размера мелководья

# --- грязь ---
MUD_CHANCE = 0.35
MUD_RADIUS = (500.0, 1400.0)

# --- камни ---
ROCK_CELL_CHANCE = 0.55
ROCKS_PER_CELL = (1, 3)
ROCK_SMALL = (80.0, 200.0)
ROCK_MEDIUM = (250.0, 450.0)
ROCK_BIG = (600.0, 1000.0)
ROCK_MEDIUM_P = 0.23
ROCK_BIG_P = 0.07
THICKNESS_SAMPLES = 72

# --- множители скорости ---
SHALLOWS_K = 0.60
MID_WATER_K = 0.40
MUD_K = 0.40

# --- масса камней ---
ROCK_DENSITY = 2.7
ROCK_SHAPE_K = 0.65
ROCK_H_BASE = 0.4
ROCK_H_K = 0.45
ROCK_H_MIN, ROCK_H_MAX = 0.5, 4.0
ROCK_ARMOR_MM = 3000.0

LAKE_VERTS, LAKE_STRETCH, LAKE_ROUGH, LAKE_JITTER = 22, (1.0, 1.5), 0.22, 0.04
MUD_VERTS, MUD_STRETCH, MUD_ROUGH, MUD_JITTER = 16, (1.0, 1.6), 0.28, 0.06
ROCK_VERTS, ROCK_STRETCH, ROCK_ROUGH, ROCK_JITTER = (7, 11), (1.0, 1.7), 0.15, 0.20

@dataclass(frozen=True)
class TerrainKind:
    name: str
    speed_k: float                 # множитель скорости: 1.0 как трава, 0.0 — нельзя
    solid: bool                    # блокирует корпус
    layer: int                     # порядок рисования: меньше — раньше
    density: float = 0.0           # т/м³; 0 — масса не считается (вода, грязь)
    armor_mm: float = 0.0          # броня для снарядов (имеет смысл, если blocks_shells)
    blocks_shells: bool = False    # останавливает снаряды
    pushable: bool = False         # можно сдвинуть тараном (если легче танка)

SHALLOWS = TerrainKind("Мелководье", SHALLOWS_K, False, 0)
MUD = TerrainKind("Грязь", MUD_K, False, 1)
MID_WATER = TerrainKind("Вода", MID_WATER_K, False, 2)
DEEP_WATER = TerrainKind("Глубокая вода", 0.0, True, 3)
ROCK = TerrainKind("Камень", 0.0, True, 4,
                   density=ROCK_DENSITY, armor_mm=ROCK_ARMOR_MM,
                   blocks_shells=True, pushable=True)

# Уровень ландшафта -> вид местности и множитель скорости (индекс = уровень сетки)
LEVEL_KINDS = (None, MUD, SHALLOWS, MID_WATER, DEEP_WATER)
LEVEL_SPEED = (1.0, MUD_K, SHALLOWS_K, MID_WATER_K, 0.0)

# ==========================================
# 2. ПЯТНО (теперь это камень; вода и грязь живут в сетке)
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

    target_type = TargetType.TERRAIN

    def __init__(self, kind, x, y, pts):
        self.kind = kind
        self.x, self.y = x, y
        self.pts = pts
        self.r_max = max(math.hypot(px - x, py - y) for px, py in pts)
        self.area_m2 = _polygon_area(pts) / (PX_PER_M * PX_PER_M)
        self.tris = self._make_tris()        # треугольники для столкновений нужны только твёрдым пятнам
        # --- подвижные камни (таран) ---
        self.vx = 0.0                        # скорость, px/с
        self.vy = 0.0
        self.cell = None                     # ячейка, в списке которой камень лежит сейчас
        self.source = None                   # RockData, из которой создан камень (редактор карт)
        self._thickness = None               # кэш thickness_stats: при сдвиге камня фигура не меняется

    def _make_tris(self):
        n = len(self.pts)
        return ([((self.x, self.y), self.pts[i], self.pts[(i + 1) % n]) for i in range(n)]
                if self.kind.solid else ())

    def move_by(self, dx, dy):
        """Сдвинуть пятно на месте (фигура и треугольники столкновений)."""
        self.x += dx
        self.y += dy
        self.pts = [(px + dx, py + dy) for px, py in self.pts]
        self.tris = self._make_tris()

    def shifted(self, dx, dy):
        """Копия пятна со сдвигом: для проверок «а если камень будет здесь?»."""
        return Patch(self.kind, self.x + dx, self.y + dy, [(px + dx, py + dy) for px, py in self.pts])

    # ---------- вес ----------
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

    def thickness_stats(self):
        """(средняя, наименьшая) толщина в метрах. Считается один раз: камень только сдвигается."""
        if self._thickness is None:
            widths = []
            for k in range(THICKNESS_SAMPLES):
                a = math.pi * k / THICKNESS_SAMPLES
                ax, ay = math.cos(a), math.sin(a)
                proj = [px * ax + py * ay for px, py in self.pts]
                widths.append(max(proj) - min(proj))
            self._thickness = (sum(widths) / len(widths) / PX_PER_M, min(widths) / PX_PER_M)
        return self._thickness

    def describe(self):
        avg, low = self.thickness_stats()
        return self.kind.name, [
            ("Средняя толщина", f"{avg:.2f} м"),
            ("Наименьшая толщина", f"{low:.2f} м"),
            ("Масса", f"{fmt_num(self.mass_t, 1)} т"),
        ]

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

    def take_hit(self, penetration, damage, cos_impact=1.0, normal=None, min_frac=0.0, caliber_mm=0.0):
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

# ==========================================
# 3. КАРТА ПРЕПЯТСТВИЙ
# ==========================================
class TerrainMap:
    """Всё о препятствиях: что где лежит, что под точкой, мешает ли прямоугольник, куда попал снаряд.
    Вода и грязь берутся из сетки (map_data.landscape), камни хранятся пятнами по ячейкам поиска."""

    def __init__(self, map_data):
        self.map = map_data
        self.grid = map_data.landscape
        self.half_w = map_data.half_w_px             # границы мира берём из самой карты
        self.half_h = map_data.half_h_px
        self._cells = {}                             # (ix, iy) -> [камни], чей центр лежит в этой ячейке
        self.rocks = RockMover(self)                 # подвижные камни (таран): толчок, скольжение, перенос
        for rd in map_data.rocks:
            patch = Patch(ROCK, rd.x, rd.y, [(px, py) for px, py in rd.pts])
            patch.source = rd
            patch.cell = self.cell_of(patch.x, patch.y)
            self._cells.setdefault(patch.cell, []).append(patch)

    @staticmethod
    def cell_of(x, y):
        """Индексы ячейки поиска, в которой лежит точка."""
        return math.floor(x / FEATURE_CELL), math.floor(y / FEATURE_CELL)

    def cached_cell(self, key):
        """Список камней ячейки (создаётся пустым, если ячейки не было). Для RockMover."""
        return self._cells.setdefault(key, [])

    # ---------- правка камней (редактор карт) ----------
    def add_rock(self, rock_data):
        """Добавляет камень в карту и в поиск. rock_data: RockData. Возвращает созданный Patch."""
        self.map.rocks.append(rock_data)
        patch = Patch(ROCK, rock_data.x, rock_data.y, [(px, py) for px, py in rock_data.pts])
        patch.source = rock_data
        patch.cell = self.cell_of(patch.x, patch.y)
        self._cells.setdefault(patch.cell, []).append(patch)
        return patch

    def remove_rock(self, patch):
        """Убирает камень из карты и из поиска (сравнение по identity, а не по равенству полей)."""
        for lst, item in ((self._cells.get(patch.cell, []), patch), (self.map.rocks, patch.source)):
            for i, obj in enumerate(lst):
                if obj is item:
                    del lst[i]
                    break

    @staticmethod
    def level_speed(level):
        return LEVEL_SPEED[level]

    # ---------- поиск камней ----------
    def _near(self, x, y, radius):
        """Пятна, чей круг (центр, r_max) пересекается с кругом (x, y, radius)."""
        reach = radius + MAX_PATCH_R
        ix0 = math.floor((x - reach) / FEATURE_CELL)
        ix1 = math.floor((x + reach) / FEATURE_CELL)
        iy0 = math.floor((y - reach) / FEATURE_CELL)
        iy1 = math.floor((y + reach) / FEATURE_CELL)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                for p in self._cells.get((ix, iy), ()):
                    dx, dy = p.x - x, p.y - y
                    lim = p.r_max + radius
                    if dx * dx + dy * dy <= lim * lim:
                        yield p

    def patches_in_rect(self, x0, y0, x1, y1):
        """Камни, которые могут попасть в прямоугольник мира (для рисования)."""
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        radius = math.hypot(x1 - x0, y1 - y0) / 2.0
        return sorted(self._near(mx, my, radius), key=lambda p: p.kind.layer)

    def patches_near(self, x, y, radius):
        """Список камней, которые могут оказаться в круге (x, y, radius). Для проверок на нескольких
        кадрах подряд не годится: список нужно брать заново (радиус берут с запасом на сдвиг за кадр)."""
        return list(self._near(x, y, radius))

    # ---------- вид местности под точкой ----------
    def kind_in(self, patches, x, y):
        """Вид местности под точкой: сетка плюс камни из списка (побеждает самый «тяжёлый»).
        None: обычная трава."""
        best = LEVEL_KINDS[self.grid.level_at(x, y)]
        for p in patches:
            if p.contains(x, y) and (best is None or p.kind.speed_k < best.speed_k):
                best = p.kind
        return best

    def speed_in(self, patches, x, y):
        kind = self.kind_in(patches, x, y)
        return 1.0 if kind is None else kind.speed_k

    # ---------- столкновения ----------
    def _hits_deep(self, cx, cy, hw, hl, ang):
        """Задевает ли повёрнутый прямоугольник клетку глубокой воды. Сначала дешёвый перебор уровней
        по рамке, и только для глубоких клеток точная проверка."""
        grid = self.grid
        if not grid.has_deep:
            return False
        rad = math.radians(ang)
        c, s = abs(math.cos(rad)), abs(math.sin(rad))
        ex = hw * c + hl * s
        ey = hw * s + hl * c
        i0, i1, j0, j1 = grid.cell_range(cx - ex, cy - ey, cx + ex, cy + ey)
        half = CELL_PX / 2.0
        data, cols = grid.data, grid.cols
        for j in range(j0, j1 + 1):
            row = j * cols
            end = row + i1 + 1
            k = data.find(L_DEEP, row + i0, end)
            while k != -1:
                x, y = grid.cell_center(k - row, j)
                if obb_hits_obb(cx, cy, hw, hl, ang, x, y, half, half, 0.0):
                    return True
                k = data.find(L_DEEP, k + 1, end)
        return False

    def deep_overlaps(self, patch):
        """Задевает ли камень глубокую воду (для скользящих камней: RockMover)."""
        grid = self.grid
        if not grid.has_deep:
            return False
        r = patch.r_max
        i0, i1, j0, j1 = grid.cell_range(patch.x - r, patch.y - r, patch.x + r, patch.y + r)
        half = CELL_PX / 2.0
        lim = r + half * 1.4143
        data, cols = grid.data, grid.cols
        for j in range(j0, j1 + 1):
            row = j * cols
            end = row + i1 + 1
            k = data.find(L_DEEP, row + i0, end)
            while k != -1:
                cx, cy = grid.cell_center(k - row, j)
                dx, dy = cx - patch.x, cy - patch.y
                if dx * dx + dy * dy <= lim * lim and any(
                        obb_hits_convex(cx, cy, half, half, 0.0, tri) for tri in patch.tris):
                    return True
                k = data.find(L_DEEP, k + 1, end)
        return False

    def blocks_obb_in(self, patches, obb):
        """Задевает ли повёрнутый прямоугольник (x, y, half_w, half_l, angle) камень из списка,
        глубокую воду или край мира. Ствол в столкновениях не участвует: проверяется только корпус."""
        cx, cy, hw, hl, ang = obb
        if obb_outside_rect(cx, cy, hw, hl, ang, -self.half_w, -self.half_h, self.half_w, self.half_h):
            return True
        for p in patches:
            if not p.kind.solid:
                continue
            dx, dy = p.x - cx, p.y - cy
            lim = p.r_max + math.hypot(hw, hl)
            if dx * dx + dy * dy > lim * lim:
                continue  # грубая отсечка по кругу
            for tri in p.tris:
                if obb_hits_convex(cx, cy, hw, hl, ang, tri):
                    return True
        return self._hits_deep(cx, cy, hw, hl, ang)

    # --- те же вопросы без заранее собранного списка (для кода вне танка) ---

    def speed_factor(self, x, y):
        return self.speed_in(self.patches_near(x, y, 0.0), x, y)

    def blocks_obb(self, obb):
        cx, cy, hw, hl, _ = obb
        return self.blocks_obb_in(self.patches_near(cx, cy, math.hypot(hw, hl)), obb)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Ближайший камень, останавливающий снаряды, на отрезке: (patch, t, normal) или None.
        Тот же формат, что у WallManager.raycast, поэтому карта подключается в TargetSet как есть.
        Вода и грязь снаряды не останавливают."""
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