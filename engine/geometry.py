"""engine/geometry.py — пересечения повёрнутых прямоугольников и отрезков."""
import math

from .mathx import heading_vector

def _obb_axes(heading_deg):
    """Две оси повёрнутого прямоугольника: (вправо, вперёд). Угол как у танка: 0 = вверх, по часовой."""
    fx, fy = heading_vector(heading_deg)
    return (-fy, fx), (fx, fy)

def obb_hits_obb(cx1, cy1, hw1, hl1, ang1, cx2, cy2, hw2, hl2, ang2):
    """Пересекаются ли два повёрнутых прямоугольника (теорема о разделяющей оси).
    Формат каждого: центр, полуширина, получастота вдоль направления, угол. Касание пересечением не считается."""
    r1, f1 = _obb_axes(ang1)
    r2, f2 = _obb_axes(ang2)
    dx, dy = cx2 - cx1, cy2 - cy1
    for ax, ay in (r1, f1, r2, f2):
        dist = abs(dx * ax + dy * ay)
        reach1 = hw1 * abs(r1[0] * ax + r1[1] * ay) + hl1 * abs(f1[0] * ax + f1[1] * ay)
        reach2 = hw2 * abs(r2[0] * ax + r2[1] * ay) + hl2 * abs(f2[0] * ax + f2[1] * ay)
        if dist >= reach1 + reach2:
            return False
    return True

def obb_hits_convex(cx, cy, half_w, half_l, angle_deg, poly):
    """Пересекается ли повёрнутый прямоугольник (центр, полуширина, полудлина, угол) с выпуклым
    многоугольником poly = [(x, y), ...] (теорема о разделяющей оси). Касание пересечением не считается."""
    r, f = _obb_axes(angle_deg)
    axes = [r, f]
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        ln = math.hypot(ex, ey)
        if ln > 1e-9:
            axes.append((-ey / ln, ex / ln))

    for ax, ay in axes:
        mid = cx * ax + cy * ay
        reach = half_w * abs(r[0] * ax + r[1] * ay) + half_l * abs(f[0] * ax + f[1] * ay)
        lo = min(px * ax + py * ay for px, py in poly)
        hi = max(px * ax + py * ay for px, py in poly)
        if hi <= mid - reach or lo >= mid + reach:
            return False
    return True

def obb_segment_hit(obb, x0, y0, x1, y1):
    """Первое пересечение отрезка с повёрнутым прямоугольником obb = (x, y, half_w, half_l, angle).
    Возвращает (t, normal) или None. t — доля пути 0..1; normal — наружная нормаль грани,
    в которую вошли (мировые координаты), либо None, если отрезок начинается внутри."""
    cx, cy, half_w, half_l, angle = obb
    rad = math.radians(angle)
    c, s = math.cos(rad), math.sin(rad)

    def to_local(x, y):
        dx, dy = x - cx, y - cy
        return dx * c + dy * s, -dx * s + dy * c

    u0, v0 = to_local(x0, y0)
    u1, v1 = to_local(x1, y1)
    t0, t1 = 0.0, 1.0
    normal_local = None
    for axis, p, q, half in ((0, u0, u1 - u0, half_w),
                             (1, v0, v1 - v0, half_l)):
        if abs(q) < 1e-9:
            if abs(p) > half:
                return None
            continue
        ta, tb = (-half - p) / q, (half - p) / q
        sign = -1.0 if q > 0 else 1.0
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
    nu, nv = normal_local
    return t0, (nu * c - nv * s, nu * s + nv * c)

def obb_outside_rect(cx, cy, half_w, half_l, angle_deg, left, top, right, bottom):
    """True, если повёрнутый прямоугольник (центр, полуширина, полудлина, угол) хоть частью
    выходит за осевую рамку left/top/right/bottom. Касание края выходом не считается."""
    rad = math.radians(angle_deg)
    c, s = abs(math.cos(rad)), abs(math.sin(rad))
    ex = half_w * c + half_l * s          # полуразмер описанной осевой рамки по X
    ey = half_w * s + half_l * c          # и по Y
    return cx - ex < left or cx + ex > right or cy - ey < top or cy + ey > bottom

def obb_contact(a, b):
    """Контакт двух повёрнутых прямоугольников a, b = (x, y, half_w, half_l, angle).
    Возвращает (глубина, nx, ny) по оси наименьшего проникновения; (nx, ny) — единичная нормаль ОТ a К b.
    None, если прямоугольники не пересекаются. Чтобы поймать «почти касание», раздуйте a на пару px."""
    cx1, cy1, hw1, hl1, ang1 = a
    cx2, cy2, hw2, hl2, ang2 = b
    r1, f1 = _obb_axes(ang1)
    r2, f2 = _obb_axes(ang2)
    dx, dy = cx2 - cx1, cy2 - cy1
    best = None
    for ax, ay in (r1, f1, r2, f2):
        proj = dx * ax + dy * ay
        reach1 = hw1 * abs(r1[0] * ax + r1[1] * ay) + hl1 * abs(f1[0] * ax + f1[1] * ay)
        reach2 = hw2 * abs(r2[0] * ax + r2[1] * ay) + hl2 * abs(f2[0] * ax + f2[1] * ay)
        depth = reach1 + reach2 - abs(proj)
        if depth <= 0.0:
            return None
        if best is None or depth < best[0]:
            sign = 1.0 if proj >= 0.0 else -1.0
            best = (depth, ax * sign, ay * sign)
    return best

def obb_convex_contact(cx, cy, half_w, half_l, angle_deg, poly):
    """Как obb_hits_convex, но возвращает (глубина, nx, ny): ось наименьшего проникновения
    и единичную нормаль ОТ прямоугольника К многоугольнику. None, если фигуры не пересекаются."""
    r, f = _obb_axes(angle_deg)
    axes = [r, f]
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        ln = math.hypot(ex, ey)
        if ln > 1e-9:
            axes.append((-ey / ln, ex / ln))

    pcx = sum(x for x, _ in poly) / n
    pcy = sum(y for _, y in poly) / n
    best = None
    for ax, ay in axes:
        mid = cx * ax + cy * ay
        reach = half_w * abs(r[0] * ax + r[1] * ay) + half_l * abs(f[0] * ax + f[1] * ay)
        lo = min(px * ax + py * ay for px, py in poly)
        hi = max(px * ax + py * ay for px, py in poly)
        depth = min(hi, mid + reach) - max(lo, mid - reach)
        if depth <= 0.0:
            return None
        if best is None or depth < best[0]:
            sign = 1.0 if (pcx - cx) * ax + (pcy - cy) * ay >= 0.0 else -1.0
            best = (depth, ax * sign, ay * sign)
    return best

def obb_distance_to_point(obb, x, y):
    """Расстояние от точки до ближайшей точки повёрнутого прямоугольника obb = (x, y, half_w, half_l, angle).
    0, если точка внутри. Система координат та же, что в obb_segment_hit."""
    cx, cy, half_w, half_l, angle = obb
    rad = math.radians(angle)
    c, s = math.cos(rad), math.sin(rad)
    dx, dy = x - cx, y - cy
    u = dx * c + dy * s
    v = -dx * s + dy * c
    return math.hypot(max(abs(u) - half_w, 0.0), max(abs(v) - half_l, 0.0))

def shrink_polygon(pts, cx, cy, k, dx=0.0, dy=0.0):
    """Уменьшить фигуру относительно центра (cx, cy) в k раз и сдвинуть на (dx, dy)."""
    return [(cx + (x - cx) * k + dx, cy + (y - cy) * k + dy) for x, y in pts]

# ==========================================
# ВЫПУКЛЫЕ МНОГОУГОЛЬНИКИ И ЛОКАЛЬНАЯ СИСТЕМА КОРПУСА
# ==========================================

_EPS = 1e-9

def _signed_area2(poly):
    """Удвоенная площадь со знаком: знак показывает направление обхода вершин."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s

def is_convex(poly):
    """Простой выпуклый многоугольник (любой порядок обхода). Звёздчатые и самопересекающиеся: False."""
    n = len(poly)
    if n < 3:
        return False
    pos = neg = False
    turn = 0.0
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        cx, cy = poly[(i + 2) % n]
        abx, aby = bx - ax, by - ay
        bcx, bcy = cx - bx, cy - by
        cross = abx * bcy - aby * bcx
        if cross > _EPS:
            pos = True
        elif cross < -_EPS:
            neg = True
        if pos and neg:
            return False
        turn += math.atan2(cross, abx * bcx + aby * bcy)
    return (pos or neg) and abs(abs(turn) - 2.0 * math.pi) < 1e-6

def point_in_convex(poly, x, y):
    """Лежит ли точка внутри выпуклого многоугольника. Точка на границе считается внутри."""
    sign = 1.0 if _signed_area2(poly) >= 0.0 else -1.0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if ((bx - ax) * (y - ay) - (by - ay) * (x - ax)) * sign < -_EPS:
            return False
    return True

def convex_segment_hit(poly, x0, y0, x1, y1):
    """Первое пересечение отрезка с выпуклым многоугольником poly = [(x, y), ...]."""
    n = len(poly)
    sign = 1.0 if _signed_area2(poly) >= 0.0 else -1.0
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    normal = None
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        ln = math.hypot(ex, ey)
        if ln < _EPS:
            continue
        nx, ny = ey * sign / ln, -ex * sign / ln          # наружная единичная нормаль
        dist = nx * (x0 - ax) + ny * (y0 - ay)            # > 0: начало отрезка снаружи ребра
        denom = nx * dx + ny * dy                         # < 0: отрезок идёт внутрь
        if abs(denom) < _EPS:                             # параллельно ребру
            if dist > 0.0:
                return None
            continue
        t = -dist / denom
        if denom < 0.0:                                   # вход
            if t > t0:
                t0 = t
                normal = (nx, ny)
        elif t < t1:                                      # выход
            t1 = t
        if t0 > t1:
            return None
    return t0, normal

def edge_normal_away(ax, ay, bx, by, rx, ry):
    """Единичная нормаль ребра ab, направленная ОТ внутренней точки (rx, ry).
    Нужна, чтобы не следить за порядком обхода вершин при задании плит."""
    ex, ey = bx - ax, by - ay
    ln = math.hypot(ex, ey)
    if ln < _EPS:
        raise ValueError("edge_normal_away: вырожденное ребро")
    nx, ny = ey / ln, -ex / ln
    side = nx * (rx - ax) + ny * (ry - ay)
    if abs(side) < _EPS:
        raise ValueError("edge_normal_away: опорная точка лежит на линии ребра")
    if side > 0.0:
        nx, ny = -nx, -ny
    return nx, ny

def to_local_frame(x, y, cx, cy, angle_deg, scale=1.0):
    """Мировая точка -> локальная (u, v). (cx, cy): начало локальной системы в мире,
    angle_deg: курс корпуса (0 = вверх, по часовой), scale: мировых px в одной локальной единице
    (для локальных метров это HULL_SCALE * PX_PER_M)."""
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    dx, dy = x - cx, y - cy
    return (dx * c + dy * s) / scale, (-dx * s + dy * c) / scale

def vec_to_local(dx, dy, angle_deg):
    """Мировой вектор (например, нормаль) -> локальный. Только поворот, без сдвига и масштаба."""
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    return dx * c + dy * s, -dx * s + dy * c

def vec_from_local(u, v, angle_deg):
    """Локальный вектор -> мировой (только поворот)."""
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    return u * c - v * s, u * s + v * c