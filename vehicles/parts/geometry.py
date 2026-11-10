"""vehicles/parts/geometry.py — геометрия детали для редактора."""
import math
from dataclasses import replace

from .model import Part
from .registry import PART_TYPES

PICK_MIN_M = 0.06            # минимальный допуск выбора, м (тонкие швы и тросы иначе не поймать)

# ==========================================
# ГАБАРИТ В ЛОКАЛЬНЫХ КООРДИНАТАХ (до отражения и поворота): (x0, y0, x1, y1)
# ==========================================

def _rect(p): return 0.0, 0.0, p.w, p.h
def _disc(p): return -p.w, -p.w, p.w, p.w
def _hang(p): return -p.w / 2.0, 0.0, p.w / 2.0, p.h          # от середины переднего края
def _seam(p): return 0.0, -0.03, p.w, 0.15                    # линия и ряд заклёпок под ней
def _flat(p): return 0.0, -0.02, p.w, 0.02
def _antenna(p): return -p.w, -p.w, p.w, p.h
def _chevron(p): return -0.40 * p.w, -0.95 * p.w, 0.40 * p.w, -0.13 * p.w

def _vline(t):
    return lambda p: (-t, 0.0, t, p.h)
def _sheet(p): return -p.w / 2.0, -0.14, p.w / 2.0, 0.14      # центр габарита = центр листа

BOUNDS = {
    "hatch": _disc, "exhaust": _disc, "dome": _disc, "turret_hatch": _disc, "loader_hatch": _disc,
    "grill": _rect, "plate": _rect, "engine_cover": _rect, "toolbox": _rect, "clamp": _rect,
    "vent_grille": _rect, "periscope": _rect, "roof_hatch": _rect, "vent": _rect, "ammo_crate": _rect,
    "ejector": _rect, "muzzle_band": _rect, "muzzle_brake": _rect,
    "seam": _seam, "roof_seam": _flat, "cable": _vline(0.04), "handle": _vline(0.03),
    "breech_tray": _hang, "embrasure": _hang, "antenna": _antenna, "chevron": _chevron,
    "screen": _sheet, "turret_screen": _sheet
}

# размер новой детали (w, h); обрезается под границы типа
DEFAULT_SIZE = {
    "hatch": (0.24, 0.0), "grill": (1.6, 1.2), "plate": (2.0, 0.5), "exhaust": (0.15, 0.0),
    "seam": (1.8, 0.0), "engine_cover": (2.0, 1.5), "toolbox": (0.3, 0.9), "cable": (0.0, 3.0),
    "handle": (0.0, 0.7), "clamp": (0.12, 0.14), "vent_grille": (1.9, 1.2), "roof_seam": (1.8, 0.0),
    "breech_tray": (1.0, 1.0), "embrasure": (1.4, 0.55), "periscope": (0.3, 0.1), "dome": (0.26, 0.15),
    "roof_hatch": (0.42, 0.40), "vent": (0.7, 0.34), "ammo_crate": (0.58, 0.45), "antenna": (0.09, 0.9),
    "chevron": (1.0, 0.0), "turret_hatch": (0.42, 0.32), "loader_hatch": (0.26, 0.0),
    "ejector": (0.4, 0.3), "muzzle_band": (0.4, 0.22), "muzzle_brake": (0.5, 0.4),
    "screen": (0.6, 0.0), "turret_screen": (0.6, 0.0)
}

def local_bounds(part):
    fn = BOUNDS.get(part.kind)
    return fn(part) if fn is not None else (-0.15, -0.15, 0.15, 0.15)

# ==========================================
# ПЕРЕВОД КООРДИНАТ
# ==========================================

def to_surface(part, u, v):
    """Локальная точка детали -> метры поверхности (отражение, затем поворот по часовой, как в PartPen)."""
    if part.mirror:
        u = -u
    rad = math.radians(part.angle)
    c, s = math.cos(rad), math.sin(rad)
    return part.x + u * c - v * s, part.y + u * s + v * c

def to_local(part, x, y):
    """Метры поверхности -> локальная точка детали."""
    rad = math.radians(part.angle)
    c, s = math.cos(rad), math.sin(rad)
    dx, dy = x - part.x, y - part.y
    u = dx * c + dy * s
    v = -dx * s + dy * c
    return (-u if part.mirror else u), v

def center(part):
    """Центр габарита детали в метрах поверхности."""
    x0, y0, x1, y1 = local_bounds(part)
    return to_surface(part, (x0 + x1) / 2.0, (y0 + y1) / 2.0)

def corners(part):
    """Четыре угла габарита в метрах поверхности (по кругу)."""
    x0, y0, x1, y1 = local_bounds(part)
    return [to_surface(part, u, v) for u, v in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]

def extent_m(part):
    """Половина диагонали габарита, м (по ней выбирается радиус дуг рукоятки)."""
    x0, y0, x1, y1 = local_bounds(part)
    return math.hypot(x1 - x0, y1 - y0) / 2.0

def contains(part, x, y, tol=0.0):
    """Лежит ли точка поверхности в габарите детали (с допуском tol, м)."""
    u, v = to_local(part, x, y)
    x0, y0, x1, y1 = local_bounds(part)
    t = max(tol, 0.0)
    return x0 - t <= u <= x1 + t and y0 - t <= v <= y1 + t

# ==========================================
# ИЗМЕНЕНИЯ ВОКРУГ ЦЕНТРА
# ==========================================

def with_center(part, cx, cy):
    """Деталь, сдвинутая так, чтобы центр габарита встал в (cx, cy)."""
    ox, oy = center(part)
    return replace(part, x=part.x + cx - ox, y=part.y + cy - oy)

def reshaped(part, **changes):
    """Изменить угол, отражение или размер, оставив центр габарита на месте."""
    cx, cy = center(part)
    return with_center(replace(part, **changes), cx, cy)

def new_part(kind, surface, cx, cy):
    """Новая деталь типа kind с размером по умолчанию, центр в (cx, cy)."""
    ptype = PART_TYPES[kind]
    dw, dh = DEFAULT_SIZE.get(kind, (0.3, 0.3))
    w = 0.0 if ptype.w_range is None else min(ptype.w_range[1], max(ptype.w_range[0], dw))
    h = 0.0 if ptype.h_range is None else min(ptype.h_range[1], max(ptype.h_range[0], dh))
    return with_center(Part(kind=kind, w=w, h=h, surface=surface), cx, cy)