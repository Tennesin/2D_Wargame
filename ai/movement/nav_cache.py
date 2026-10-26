"""ai/movement/nav_cache.py — кэш рельефа для A*: расстояние до твёрдых пятен и вязкость по клеткам."""
import math

from vehicles.chassis.params import TERRAIN_MIN_K
from engine import PX_PER_M, LRUCache

CELL_PX = 3.0 * PX_PER_M          # размер клетки, px мира
NAV_CAP_PX = 8.0 * PX_PER_M       # дальше этого расстояния до препятствия клетка «свободна»; должно быть больше любого радиуса танка
CHUNK_CELLS = 8                   # сторона блока кэша, клеток (8 × 3 м = 24 м)
CACHE_CHUNKS = 400                # сколько блоков держим в памяти

def seg_dist2(px, py, ax, ay, bx, by):
    """Квадрат расстояния от точки до отрезка ab."""
    abx, aby = bx - ax, by - ay
    ln = abx * abx + aby * aby
    t = 0.0 if ln <= 1e-9 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ln))
    dx, dy = ax + abx * t - px, ay + aby * t - py
    return dx * dx + dy * dy

def _polygon_dist(patch, x, y, cap):
    """Расстояние от точки до пятна: 0 внутри, иначе до ближайшего ребра, но не больше cap."""
    if patch.contains(x, y):
        return 0.0
    best2 = cap * cap
    pts = patch.pts
    ax, ay = pts[-1]
    for bx, by in pts:
        d2 = seg_dist2(x, y, ax, ay, bx, by)
        if d2 < best2:
            best2 = d2
        ax, ay = bx, by
    return math.sqrt(best2)

# ==========================================
# КЭШ РЕЛЬЕФА
# ==========================================

class TerrainNavCache:
    """Глобальная сетка клеток CELL_PX. Для каждой клетки хранит: расстояние до ближайшего твёрдого пятна
    (0 внутри; NAV_CAP_PX, если дальше) и множитель времени от вязкой местности.
    Блок строится при первом обращении и сбрасывается, когда рядом сдвинули камень."""

    def __init__(self, terrain):
        self.terrain = terrain
        self._chunks = LRUCache(CACHE_CHUNKS)
        terrain.rocks.add_move_listener(self.invalidate_circle)

    def chunk(self, ci, cj):
        """(dist, slow): два списка по CHUNK_CELLS² значений, строки подряд."""
        return self._chunks.get_or_build((ci, cj), lambda: self._build(ci, cj))

    def invalidate_circle(self, x, y, r):
        """Сбросить блоки, в которых что-то могло измениться из-за пятна (x, y, r)."""
        span = CHUNK_CELLS * CELL_PX
        reach = r + NAV_CAP_PX
        for cj in range(math.floor((y - reach) / span), math.floor((y + reach) / span) + 1):
            for ci in range(math.floor((x - reach) / span), math.floor((x + reach) / span) + 1):
                self._chunks.discard((ci, cj))

    def _build(self, ci, cj):
        B = CHUNK_CELLS
        span = B * CELL_PX
        x_lo, y_lo = ci * span, cj * span
        half = span / 2.0
        terrain = self.terrain
        grid = terrain.grid
        patches = terrain.patches_near(x_lo + half, y_lo + half, half * 1.4143 + NAV_CAP_PX)
        deep_edges = grid.deep_edges_in(x_lo - NAV_CAP_PX, y_lo - NAV_CAP_PX,
                                        x_lo + span + NAV_CAP_PX, y_lo + span + NAV_CAP_PX)
        cell_half = grid.cell_center(0, 0)[0] - (-grid.half_w_px)       # полклетки ландшафта

        dist = [NAV_CAP_PX] * (B * B)
        slow = [1.0] * (B * B)

        # вода и грязь из сетки: вязкость по клетке, расстояние до глубокой воды по её береговым клеткам
        for j in range(B):
            y = y_lo + (j + 0.5) * CELL_PX
            for i in range(B):
                x = x_lo + (i + 0.5) * CELL_PX
                k = j * B + i
                level = grid.level_at(x, y)
                if level == grid.DEEP:
                    dist[k] = 0.0
                    continue
                if level != grid.GRASS:
                    slow[k] = 1.0 / max(terrain.level_speed(level), TERRAIN_MIN_K)
                for cx, cy in deep_edges:
                    ddx = abs(x - cx) - cell_half
                    if ddx >= dist[k]:
                        continue
                    ddy = abs(y - cy) - cell_half
                    if ddy >= dist[k]:
                        continue
                    d = math.hypot(max(ddx, 0.0), max(ddy, 0.0))
                    if d < dist[k]:
                        dist[k] = d

        # камни (твёрдые многоугольники)
        for p in patches:
            if not p.kind.solid:
                continue
            lim = p.r_max + NAV_CAP_PX
            lim2 = lim * lim
            for j in range(B):
                y = y_lo + (j + 0.5) * CELL_PX
                for i in range(B):
                    x = x_lo + (i + 0.5) * CELL_PX
                    dx, dy = x - p.x, y - p.y
                    if dx * dx + dy * dy > lim2:
                        continue
                    k = j * B + i
                    d = _polygon_dist(p, x, y, NAV_CAP_PX)
                    if d < dist[k]:
                        dist[k] = d
        return dist, slow