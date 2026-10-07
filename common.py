"""common.py — общее для мира и техники: масштаб, математика, команда машине, событие выстрела.
Не импортирует ни core, ни tank, поэтому циклических импортов не возникает."""
import math
from dataclasses import dataclass
from typing import Optional, Tuple

# ==========================================
# 1. МАСШТАБ
# ==========================================
PX_PER_M = 100.0          # МАСШТАБ МИРА: 100 px = 1 метр (все скорости и расстояния в метрах переводим через него)

@dataclass(frozen=True)
class Param:
    label: str       # подпись на панели
    unit: str        # единица измерения
    min: float
    max: float
    default: float   # стартовое значение
    step: float      # шаг ползунка
    decimals: int = 0   # знаков после запятой на панели

# ==========================================
# 2. МАТЕМАТИЧЕСКИЕ ПОМОЩНИКИ
# ==========================================

def normalize_angle(angle):
    return angle % 360.0

def shortest_angle_diff(target, current):
    """Кратчайшая разница углов в диапазоне [-180, 180)."""
    return (target - current + 180.0) % 360.0 - 180.0

def clamp(value, low, high):
    return max(low, min(high, value))

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))

def _obb_axes(heading_deg):
    """Две оси повёрнутого прямоугольника: (вправо, вперёд). Угол как у танка: 0 = вверх, по часовой."""
    rad = math.radians(heading_deg)
    fx, fy = math.sin(rad), -math.cos(rad)
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

# ==========================================
# 3. КОМАНДА МАШИНЕ И СОБЫТИЕ ВЫСТРЕЛА
# ==========================================
@dataclass
class VehicleCommand:
    """Что машине «приказали» в этом кадре. Кто приказал (игрок или бот) — не важно."""
    throttle: float = 0.0                              # -1..1 (назад / вперёд)
    steer: float = 0.0                                 # -1..1 (влево / вправо)
    aim_point: Optional[Tuple[float, float]] = None    # куда целиться (МИРОВЫЕ координаты)
    fire: bool = False                                 # задел под стрельбу

@dataclass
class Shot:
    """Событие «выстрел»: откуда вылетел снаряд и куда смотрел ствол."""
    x: float          # мировые координаты дульного среза
    y: float
    angle: float      # абсолютный угол башни в градусах (0 = вверх, по часовой)