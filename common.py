"""common.py — общее для мира и техники: масштаб, математика, команда машине, событие выстрела.
Не импортирует ни core, ни tank, поэтому циклических импортов не возникает."""
import math
from dataclasses import dataclass
from typing import Optional, Tuple

# ==========================================
# 1. МАСШТАБ
# ==========================================
PX_PER_M = 100.0          # МАСШТАБ МИРА: 100 px = 1 метр (все скорости и расстояния в метрах переводим через него)

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