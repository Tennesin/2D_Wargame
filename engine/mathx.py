import math

# ==========================================
# МАТЕМАТИЧЕСКИЕ ПОМОЩНИКИ
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

def heading_vector(angle_deg):
    """Единичный вектор «вперёд» для угла (0 = вверх, по часовой): (x, y) в экранных/мировых осях."""
    rad = math.radians(angle_deg)
    return math.sin(rad), -math.cos(rad)

def find_free_fraction(is_blocked, iterations=8):
    """Бисекция: наибольшая доля пути 0..1, при которой is_blocked(доля) ещё False.
    Вызывать, когда известно, что при 0 свободно, а при 1 занято."""
    lo, hi = 0.0, 1.0
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if is_blocked(mid):
            hi = mid
        else:
            lo = mid
    return lo

def fmt_num(value, decimals=0):
    """Число с пробелом между тысячами: fmt_num(2400) -> '2 400'."""
    return f"{value:,.{decimals}f}".replace(",", " ")