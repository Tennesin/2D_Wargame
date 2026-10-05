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

def obb_hits_rect(cx, cy, half_w, half_l, heading_deg, rect):
    """Пересекается ли повёрнутый прямоугольник (корпус танка) с осевым rect = (left, top, right, bottom).
    Прямоугольник: центр (cx, cy), half_w — полуширина, half_l — полудлина вдоль направления heading_deg.
    Простое касание пересечением не считается."""
    left, top, right, bottom = rect
    rad = math.radians(heading_deg)
    fx, fy = math.sin(rad), -math.cos(rad)      # вперёд
    rx, ry = -fy, fx                            # вправо

    xs, ys = [], []
    for sw in (-half_w, half_w):
        for sl in (-half_l, half_l):
            xs.append(cx + rx * sw + fx * sl)
            ys.append(cy + ry * sw + fy * sl)

    # оси самого rect (X и Y)
    if max(xs) <= left or min(xs) >= right:
        return False
    if max(ys) <= top or min(ys) >= bottom:
        return False

    # оси повёрнутого прямоугольника
    dx = (left + right) / 2.0 - cx
    dy = (top + bottom) / 2.0 - cy
    rhw = (right - left) / 2.0
    rhh = (bottom - top) / 2.0
    for ax, ay, half in ((rx, ry, half_w), (fx, fy, half_l)):
        dist = abs(dx * ax + dy * ay)
        reach = half + rhw * abs(ax) + rhh * abs(ay)
        if dist >= reach:
            return False
    return True

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