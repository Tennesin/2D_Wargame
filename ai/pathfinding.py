"""ai/pathfinding.py — локальная навигационная сетка и A* для ботов.
Сетка строится вокруг бота при каждом перепланировании (окно 120x120 м, клетка 3 м).
Препятствия раздуты на радиус танка, поэтому сам путь можно считать путём точки.
Пробиваемая стена не блокирует клетку, а добавляет к её цене время разрушения."""
import heapq
import math

from engine import PX_PER_M, WORLD_HALF_PX, LRUCache
from .gunnery import seconds_to_break, BREACH_MAX_S, MIN_USEFUL_DAMAGE

# ==========================================
# НАСТРОЙКИ
# ==========================================
CELL_PX = 3.0 * PX_PER_M          # размер клетки, px мира
HALF_CELLS = 20                   # окно = 2*HALF_CELLS клеток по каждой оси (40x40 = 120x120 м)
N = 2 * HALF_CELLS
HEURISTIC_W = 1.2                 # взвешенный A*: быстрее, путь чуть длиннее оптимального
MAX_EXPANDED = 1800               # предел раскрытых клеток
NAV_MARGIN_PX = 0.5 * PX_PER_M    # запас к радиусу танка
CORE_MARGIN_PX = 0.3 * PX_PER_M   # запас к полуширине корпуса для «жёсткой» зоны
RELEASE_CELLS = 2                 # вокруг старта «раздутые» клетки освобождаются в этом радиусе
RELEASE_PENALTY_PX = 150.0        # цена входа в освобождённую клетку (пусть путь выходит из зоны быстрее)
MIN_SPEED_K = 0.15                # как в TERRAIN_MIN_K у танка: цена клетки не растёт бесконечно
WALL_EST_COS = 0.85               # при оценке стены берём «средний» угол попадания
STUCK_RADIUS_PX = 5.0 * PX_PER_M  # радиус штрафа вокруг места, где бот застрял
STUCK_PENALTY_PX = 1500.0         # штраф клетки, в px пути (15 м)
ARRIVE_PX = 3.0 * PX_PER_M        # на таком расстоянии от точки пути считаем её пройденной
NAV_CAP_PX = 8.0 * PX_PER_M       # дальше этого расстояния до препятствия клетка «свободна»; должно быть больше любого радиуса танка
CHUNK_CELLS = 8                   # сторона блока кэша, клеток (8 × 3 м = 24 м)
CACHE_CHUNKS = 400                # сколько блоков держим в памяти

_D = CELL_PX * 1.4142135
_NEIGH = ((1, 0, CELL_PX), (-1, 0, CELL_PX), (0, 1, CELL_PX), (0, -1, CELL_PX),
          (1, 1, _D), (1, -1, _D), (-1, 1, _D), (-1, -1, _D))

def _seg_dist2(px, py, ax, ay, bx, by):
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
        d2 = _seg_dist2(x, y, ax, ay, bx, by)
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
        patches = self.terrain.patches_near(x_lo + half, y_lo + half, half * 1.4143 + NAV_CAP_PX)

        dist = [NAV_CAP_PX] * (B * B)
        slow = [1.0] * (B * B)
        for p in patches:
            solid = p.kind.solid
            slow_k = 1.0 / max(p.kind.speed_k, MIN_SPEED_K)
            lim = p.r_max + (NAV_CAP_PX if solid else 0.0)
            lim2 = lim * lim
            for j in range(B):
                y = y_lo + (j + 0.5) * CELL_PX
                for i in range(B):
                    x = x_lo + (i + 0.5) * CELL_PX
                    dx, dy = x - p.x, y - p.y
                    if dx * dx + dy * dy > lim2:
                        continue
                    k = j * B + i
                    if solid:
                        d = _polygon_dist(p, x, y, NAV_CAP_PX)
                        if d < dist[k]:
                            dist[k] = d
                    elif slow_k > slow[k] and p.contains(x, y):
                        slow[k] = slow_k
        return dist, slow

# ==========================================
# ПУТЬ
# ==========================================
class Path:
    """Список точек (мировые px). breach_wall — первая стена на пути (её придётся ломать) или None.
    reached: путь доходит до запрошенной (возможно, обрезанной окном) цели."""

    def __init__(self, points, goal, breach_wall, reached=True):
        self.points = points
        self.goal = goal              # исходная цель запроса (не обрезанная окном)
        self.breach_wall = breach_wall
        self.reached = reached
        self.idx = 1 if len(points) > 1 else 0

    def next_point(self, x, y):
        """Ближайшая непройденная точка пути."""
        pts = self.points
        last = len(pts) - 1
        while self.idx < last:
            px, py = pts[self.idx]
            if (px - x) ** 2 + (py - y) ** 2 >= ARRIVE_PX ** 2:
                break
            self.idx += 1
        return pts[self.idx]

    def done(self, x, y):
        """Бот дошёл до конца пути."""
        px, py = self.points[-1]
        return self.idx >= len(self.points) - 1 and (px - x) ** 2 + (py - y) ** 2 < ARRIVE_PX ** 2

    def deviation_px(self, x, y):
        """Насколько бот ушёл от текущего отрезка пути."""
        if len(self.points) < 2:
            return 0.0
        i = max(1, self.idx)
        ax, ay = self.points[i - 1]
        bx, by = self.points[i]
        return math.sqrt(_seg_dist2(x, y, ax, ay, bx, by))

# ==========================================
# СЕТКА
# ==========================================
class NavGrid:
    def __init__(self, cx, cy, radius, core_radius, nav, walls, me,
                 forbidden=(), bad_spots=(), no_breach=False):
        # окно привязано к глобальной сетке, чтобы клетки совпадали с блоками кэша
        self.gi0 = math.floor(cx / CELL_PX) - HALF_CELLS
        self.gj0 = math.floor(cy / CELL_PX) - HALF_CELLS
        self.x0 = self.gi0 * CELL_PX
        self.y0 = self.gj0 * CELL_PX
        self.radius = radius               # «безопасный» радиус: раздувание препятствий
        self.core_radius = core_radius     # «жёсткий» радиус: корпус здесь физически не поместится
        self.blocked = bytearray(N * N)
        self.core = bytearray(N * N)       # подмножество blocked: зона, из которой не выпускаем
        self.slow = [1.0] * (N * N)        # множитель времени: 1 / скорость_местности
        self.extra = [0.0] * (N * N)       # добавка к цене клетки (стены, места застревания), px пути
        self.wall_at = {}                  # индекс клетки -> стена, которую придётся ломать
        self._fill_terrain(nav)
        self._fill_walls(walls, me, forbidden, no_breach)
        self._fill_bad_spots(bad_spots)
        self._fill_border(cx, cy)

    # ---------- помощники ----------
    def center(self, i, j):
        return self.x0 + (i + 0.5) * CELL_PX, self.y0 + (j + 0.5) * CELL_PX

    def _box(self, x, y, r):
        """Диапазон клеток, накрывающих круг (x, y, r): i0, i1, j0, j1 (может быть пустым)."""
        i0 = max(0, int((x - r - self.x0) // CELL_PX))
        i1 = min(N - 1, int((x + r - self.x0) // CELL_PX))
        j0 = max(0, int((y - r - self.y0) // CELL_PX))
        j1 = min(N - 1, int((y + r - self.y0) // CELL_PX))
        return i0, i1, j0, j1

    # ---------- заполнение ----------
    def _fill_terrain(self, nav):
        """Рельеф берём из кэша: клетка заблокирована, если до твёрдого пятна ближе радиуса танка."""
        R, Rc = self.radius, self.core_radius
        B = CHUNK_CELLS
        gi0, gj0 = self.gi0, self.gj0
        blocked, core, slow = self.blocked, self.core, self.slow
        for cj in range(gj0 // B, (gj0 + N - 1) // B + 1):
            for ci in range(gi0 // B, (gi0 + N - 1) // B + 1):
                dist, chunk_slow = nav.chunk(ci, cj)
                i_lo, i_hi = max(ci * B, gi0), min(ci * B + B, gi0 + N)
                j_lo, j_hi = max(cj * B, gj0), min(cj * B + B, gj0 + N)
                for gj in range(j_lo, j_hi):
                    src = (gj - cj * B) * B - ci * B          # + gi даёт индекс в блоке
                    dst = (gj - gj0) * N - gi0                # + gi даёт индекс в окне
                    for gi in range(i_lo, i_hi):
                        d = dist[src + gi]
                        idx = dst + gi
                        if d < R:
                            blocked[idx] = 1
                            if d < Rc:
                                core[idx] = 1
                        slow[idx] = chunk_slow[src + gi]

    def _fill_walls(self, walls, me, forbidden, no_breach):
        R, Rc = self.radius, self.core_radius
        est_speed = max(me.spec.v_avg, 5.0) / 3.6 * PX_PER_M          # px/с: чтобы перевести секунды в px пути
        for w in walls.items:
            if not w.alive:
                continue
            per_cell = None                                           # None: непроходима
            if not no_breach and id(w) not in forbidden:
                secs = seconds_to_break(me, w, WALL_EST_COS, None, MIN_USEFUL_DAMAGE)
                if secs is not None and secs <= BREACH_MAX_S:
                    cells_across = max(1, math.ceil((w.thickness_m * PX_PER_M + 2.0 * R) / CELL_PX))
                    per_cell = secs * est_speed / cells_across
            i0, i1, j0, j1 = self._box(w.x, w.y, w.radius_px + R)
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    x, y = self.center(i, j)
                    u, v = w.to_local(x, y)
                    du = max(abs(u) - w.half_w_px, 0.0)
                    dv = max(abs(v) - w.half_l_px, 0.0)
                    d2 = du * du + dv * dv
                    if d2 >= R * R:
                        continue
                    idx = j * N + i
                    if per_cell is None:
                        self.blocked[idx] = 1
                        if d2 < Rc * Rc:
                            self.core[idx] = 1
                    else:
                        self.extra[idx] += per_cell
                        self.wall_at.setdefault(idx, w)

    def _fill_bad_spots(self, spots):
        for sx, sy, _ttl in spots:
            i0, i1, j0, j1 = self._box(sx, sy, STUCK_RADIUS_PX)
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    x, y = self.center(i, j)
                    if (x - sx) ** 2 + (y - sy) ** 2 <= STUCK_RADIUS_PX ** 2:
                        self.extra[j * N + i] += STUCK_PENALTY_PX

    def _fill_border(self, cx, cy):
        """Клетки у края мира (танк не должен упираться в границу)."""
        reach = HALF_CELLS * CELL_PX + self.radius
        if abs(cx) + reach <= WORLD_HALF_PX and abs(cy) + reach <= WORLD_HALF_PX:
            return
        lim = WORLD_HALF_PX - self.radius
        for j in range(N):
            for i in range(N):
                x, y = self.center(i, j)
                if abs(x) > lim or abs(y) > lim:
                    self.blocked[j * N + i] = 1
                    self.core[j * N + i] = 1

    # ---------- линия видимости и сглаживание ----------
    def _los(self, i0, j0, i1, j1):
        """Прямая между центрами клеток свободна: нет препятствий, стен и вязкой местности."""
        steps = max(abs(i1 - i0), abs(j1 - j0)) * 3
        for s in range(1, steps):
            t = s / steps
            idx = int(j0 + (j1 - j0) * t + 0.5) * N + int(i0 + (i1 - i0) * t + 0.5)
            if self.blocked[idx] or self.extra[idx] > 0.0 or self.slow[idx] > 1.01:
                return False
        return True

    def _smooth(self, cells):
        """«Натягивание нити»: убираем лишние промежуточные клетки."""
        if len(cells) <= 2:
            return cells
        out = [cells[0]]
        k = 0
        while k < len(cells) - 1:
            j = len(cells) - 1
            while j > k + 1 and not self._los(cells[k][0], cells[k][1], cells[j][0], cells[j][1]):
                j -= 1
            out.append(cells[j])
            k = j
        return out

    # ---------- поиск ----------
    def search(self, sx, sy, gx, gy):
        """A* от (sx, sy) до (gx, gy). Если цель вне окна или недостижима, ведёт к ближайшей к ней
        достижимой клетке. Возвращает Path или None."""
        goal_req = (gx, gy)
        # цель за пределами окна: проецируем на его границу по прямой от бота
        dx, dy = gx - sx, gy - sy
        margin = (HALF_CELLS - 1) * CELL_PX
        far = max(abs(dx), abs(dy))
        if far > margin:
            k = margin / far
            gx, gy = sx + dx * k, sy + dy * k

        si = min(N - 1, max(0, int((sx - self.x0) // CELL_PX)))
        sj = min(N - 1, max(0, int((sy - self.y0) // CELL_PX)))
        gi = min(N - 1, max(0, int((gx - self.x0) // CELL_PX)))
        gj = min(N - 1, max(0, int((gy - self.y0) // CELL_PX)))

        # Бот мог оказаться в «раздутой» зоне (камень рядом): выпускаем его.
        # Освобождаем клетки в радиусе RELEASE_CELLS, кроме «жёсткого» ядра (там корпус не поместится);
        # сама стартовая клетка освобождается всегда.
        for dj in range(-RELEASE_CELLS, RELEASE_CELLS + 1):
            for di in range(-RELEASE_CELLS, RELEASE_CELLS + 1):
                ni, nj = si + di, sj + dj
                if not (0 <= ni < N and 0 <= nj < N):
                    continue
                k = nj * N + ni
                if self.blocked[k] and (not self.core[k] or (di == 0 and dj == 0)):
                    self.blocked[k] = 0
                    self.extra[k] += RELEASE_PENALTY_PX

        start, goal = sj * N + si, gj * N + gi
        if start == goal:
            return Path([(sx, sy), (gx, gy)], goal_req, None, True)

        blocked, slow, extra = self.blocked, self.slow, self.extra
        inf = float("inf")
        g = [inf] * (N * N)
        parent = [-1] * (N * N)
        closed = bytearray(N * N)

        def heur(i, j):
            ddx, ddy = abs(i - gi), abs(j - gj)
            return (max(ddx, ddy) + 0.4142 * min(ddx, ddy)) * CELL_PX

        g[start] = 0.0
        heap = [(HEURISTIC_W * heur(si, sj), start)]
        best, best_h = start, heur(si, sj)
        expanded = 0
        while heap and expanded < MAX_EXPANDED:
            _, cur = heapq.heappop(heap)
            if closed[cur]:
                continue
            closed[cur] = 1
            if cur == goal:
                best = goal
                break
            expanded += 1
            ci, cj = cur % N, cur // N
            hc = heur(ci, cj)
            if hc < best_h:
                best_h, best = hc, cur
            gc = g[cur]
            for di, dj, step in _NEIGH:
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < N and 0 <= nj < N):
                    continue
                nidx = nj * N + ni
                if closed[nidx] or blocked[nidx]:
                    continue
                if di and dj and (blocked[cj * N + ni] or blocked[nj * N + ci]):
                    continue                          # по диагонали через угол препятствия не режем
                ng = gc + step * 0.5 * (slow[cur] + slow[nidx]) + extra[nidx]
                if ng < g[nidx]:
                    g[nidx] = ng
                    parent[nidx] = cur
                    heapq.heappush(heap, (ng + HEURISTIC_W * heur(ni, nj), nidx))

        if best == start:
            return None
        cells_idx = []
        c = best
        while c != -1:
            cells_idx.append(c)
            c = parent[c]
        cells_idx.reverse()

        breach = None                                # первая стена, через которую идёт путь
        for c in cells_idx[1:]:
            w = self.wall_at.get(c)
            if w is not None and w.alive:
                breach = w
                break

        cells = self._smooth([(c % N, c // N) for c in cells_idx])
        points = [self.center(i, j) for i, j in cells]
        points[0] = (sx, sy)
        if best == goal:
            points[-1] = (gx, gy)
        return Path(points, goal_req, breach, best == goal)

def find_path(me, goal, walls, nav, forbidden=(), bad_spots=(), no_breach=False):
    """Путь для танка me к точке goal = (x, y) или None."""
    spec = me.spec
    hw, hl = spec.COLLISION_HALF_W_PX, spec.COLLISION_HALF_L_PX
    big = math.hypot(hw, hl) + NAV_MARGIN_PX
    tight = (hw + hl) / 2.0 + NAV_MARGIN_PX
    core = hw + CORE_MARGIN_PX

    first = None
    for radius in (big, tight):
        grid = NavGrid(me.x, me.y, radius, core, nav, walls, me, forbidden, bad_spots, no_breach)
        path = grid.search(me.x, me.y, goal[0], goal[1])
        if path is not None and path.reached:
            return path
        if first is None:
            first = path
    return first

class PlanBudget:
    """Сколько путей можно построить в одном кадре на всех ботов вместе.
    Бот, которому не хватило, продолжает ехать по старому пути и повторит попытку при следующем «размышлении»."""

    def __init__(self, per_frame=1):
        self.per_frame = per_frame
        self.left = per_frame
        self.taken = 0          # всего выдано (для замера)
        self.denied = 0         # всего отказано

    def new_frame(self):
        self.left = self.per_frame

    def try_take(self):
        if self.left > 0:
            self.left -= 1
            self.taken += 1
            return True
        self.denied += 1
        return False