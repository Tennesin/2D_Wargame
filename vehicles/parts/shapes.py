"""vehicles/parts/shapes.py — контуры башен ОБТ в метрах эталонной башни."""
from functools import lru_cache

HEX_POINTS = [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00), (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)]
HEX_INNER = [(-0.48, -1.05), (0.48, -1.05), (0.88, 0.00), (0.48, 1.12), (-0.48, 1.12), (-0.88, 0.00)]
OVAL_RECT = (-1.00, -1.15, 2.00, 2.70)           # x, y, w, h (скругление углов не учитываем)

SLAB_HALF_W = 1.30
SLAB_FRONT = 1.55
SLAB_REAR = 1.45
SLAB_FRONT_CHAMFER = (0.55, 0.60)
SLAB_REAR_CHAMFER = (0.30, 0.30)

TURRET_FIT_K = 1.10      # запас области «помещается»: антенна и люки у края могут чуть выступать

def slab_points(inset=0.0, front_extra=0.0):
    """Контур плитчатой башни: плоский лоб, срезанные передние углы, параллельные борта, плоская корма."""
    w = SLAB_HALF_W - inset
    f = SLAB_FRONT - inset - front_extra
    r = SLAB_REAR - inset
    fcx, fcy = SLAB_FRONT_CHAMFER
    rcx, rcy = SLAB_REAR_CHAMFER
    return [(-(w - fcx), -f), (w - fcx, -f), (w, -f + fcy), (w, r - rcy),
            (w - rcx, r), (-(w - rcx), r), (-w, r - rcy), (-w, -f + fcy)]

@lru_cache(maxsize=None)
def turret_outline(style):
    """Выпуклый контур башни по стилю раскладки ("hex", "oval", "slab")."""
    if style == "oval":
        x, y, w, h = OVAL_RECT
        return ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    if style == "slab":
        return tuple(slab_points())
    return tuple(HEX_POINTS)

@lru_cache(maxsize=None)
def turret_fit_outline(style):
    """Область центров деталей башни: контур с запасом TURRET_FIT_K."""
    return tuple((x * TURRET_FIT_K, y * TURRET_FIT_K) for x, y in turret_outline(style))