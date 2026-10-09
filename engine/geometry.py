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