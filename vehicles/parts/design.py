"""vehicles/parts/design.py — дизайн деталей техники."""
import math
from dataclasses import dataclass, replace
from typing import Optional

from engine import point_in_convex
from vehicles.gun.params import BARREL_HIDDEN_M, BARREL_THICK_STEP_M
from .model import Part, SURFACES, SURFACE_HULL, SURFACE_TURRET, SURFACE_BARREL, ANCHOR_HULL
from .registry import PART_TYPES
from .geometry import center, corners
from .shapes import turret_outline, turret_fit_outline

BARREL_OVERHANG_M = 0.15     # насколько деталь может выступать за боковую кромку ствола

FORMAT_VERSION = 1
LIMITS = {SURFACE_HULL: 60, SURFACE_TURRET: 40, SURFACE_BARREL: 8}   # деталей на поверхность
COORD_LIMIT_M = 8.0          # координаты подрезаются по модулю до этого значения
VARIANT_MAX = 9
Z_MAX = 99
EDGE_EPS_M = 1e-6

# Допустимые якоря. «hull» везде означает «начало координат поверхности» (абсолютные метры).
ANCHOR_NAMES = {
    SURFACE_HULL: (ANCHOR_HULL, "deck_front", "deck_rear", "nose_tip", "rear_plate",
                   "fender_left", "fender_right"),
    SURFACE_TURRET: (ANCHOR_HULL, "turret", "turret_front", "turret_rear"),
    SURFACE_BARREL: (ANCHOR_HULL, "mid", "breech", "muzzle"),
}
# К каким якорям привязываются детали при редактировании и «заморозке» (корпус остаётся в абсолютных метрах)
ANCHOR_CANDIDATES = {
    SURFACE_HULL: ("deck_front", "deck_rear", "nose_tip", "rear_plate"),
    SURFACE_TURRET: ("turret", "turret_front", "turret_rear"),
    SURFACE_BARREL: ("muzzle", "mid", "breech"),
}

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)

def _limit(v, lo, hi):
    return min(hi, max(lo, v))

# ==========================================
# ЯКОРЯ И «ПОМЕЩАЕТСЯ»
# ==========================================

def anchors(spec, surface):
    """{имя: (x, y)}: где якоря поверхности у этой техники (метры поверхности).
    Нет якоря у этой раскладки (например, подкрылков у тяжёлого): имени нет в словаре."""
    out = {ANCHOR_HULL: (0.0, 0.0)}
    if surface == SURFACE_HULL:
        lay = spec.layout
        dx, dy, dw, dh = lay.deck_rect
        px, py, pw, _ = lay.rear_plate
        out["deck_front"] = (dx + dw / 2.0, dy)
        out["deck_rear"] = (dx + dw / 2.0, dy + dh)
        out["nose_tip"] = (0.0, min(y for _, y in lay.outline))
        out["rear_plate"] = (px + pw / 2.0, py)
        if len(lay.fender_rects) >= 2:                  # порядок в раскладке: правый, левый
            (rx, ry, rw, _), (lx, ly, lw, _) = lay.fender_rects
            out["fender_right"] = (rx + rw / 2.0, ry)
            out["fender_left"] = (lx + lw / 2.0, ly)
    elif surface == SURFACE_TURRET:
        out["turret"] = (0.0, 0.0)
        out["turret_front"] = (0.0, -spec.GUN_FRONT_M)
        out["turret_rear"] = (0.0, max(y for _, y in turret_outline(spec.layout.turret_style)))
    else:
        half = (spec.BARREL_LEN_M + BARREL_HIDDEN_M) / 2.0
        out["mid"] = (0.0, 0.0)
        out["breech"] = (0.0, half)
        out["muzzle"] = (0.0, -half)
    return out

def _in_rect(x0, y0, x1, y1, x, y):
    e = EDGE_EPS_M
    return x0 - e <= x <= x1 + e and y0 - e <= y <= y1 + e

def barrel_thick_m(spec):
    """Толщина ствола, как её рисует рендерер (с квантованием)."""
    return round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M) * BARREL_THICK_STEP_M

def barrel_box(spec):
    """(x0, y0, x1, y1): область центров деталей ствола. По x это сам ствол,
    по y видимая часть: от дульного среза до начала участка под башней или маской."""
    half = (spec.BARREL_LEN_M + BARREL_HIDDEN_M) / 2.0
    hw = barrel_thick_m(spec) / 2.0
    return -hw, -half, hw, half - BARREL_HIDDEN_M

def fits(p, spec, surface):
    """Помещается ли деталь: центр её габарита лежит в допустимой области."""
    x, y = center(p)
    if surface == SURFACE_HULL:
        lay = spec.layout
        if point_in_convex(lay.outline, x, y):
            return True
        if any(_in_rect(fx, fy, fx + fw, fy + fh, x, y) for fx, fy, fw, fh in lay.fender_rects):
            return True
        return any(_in_rect(*r, x, y) for r in lay.track_rects)    # ящики и трос на экранах
    if surface == SURFACE_TURRET:
        return point_in_convex(turret_fit_outline(spec.layout.turret_style), x, y)
    x0, y0, x1, y1 = barrel_box(spec)
    if not _in_rect(x0, y0, x1, y1, x, y):
        return False
    lim = x1 + BARREL_OVERHANG_M + EDGE_EPS_M        # и сама деталь не может быть шире ствола + вылет
    return all(abs(cx) <= lim for cx, _ in corners(p))

def fit_polygons(spec, surface):
    """Многоугольники допустимой области поверхности."""
    def box(x0, y0, x1, y1):
        return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    if surface == SURFACE_HULL:
        lay = spec.layout
        polys = [tuple(lay.outline)]
        polys += [box(fx, fy, fx + fw, fy + fh) for fx, fy, fw, fh in lay.fender_rects]
        polys += [box(*r) for r in lay.track_rects]
        return polys
    if surface == SURFACE_TURRET:
        return [turret_fit_outline(spec.layout.turret_style)]
    x0, y0, x1, y1 = barrel_box(spec)
    return [box(x0, y0, x1, y1)]

def resolve(parts, spec, surface):
    """Ручные детали -> то, что рисует рендерер: абсолютные координаты, только помещающиеся.
    Не поместившиеся пропускаются, сами данные не трогаются."""
    table = anchors(spec, surface)
    out = []
    for p in parts:
        base = table.get(p.anchor)
        if base is None:
            continue
        if p.anchor != ANCHOR_HULL:
            p = replace(p, x=p.x + base[0], y=p.y + base[1], anchor=ANCHOR_HULL)
        if fits(p, spec, surface):
            out.append(p)
    return tuple(out)

def anchor_part(p, spec, surface):
    """Деталь в абсолютных метрах -> та же деталь, привязанная к ближайшему якорю поверхности."""
    names = ANCHOR_CANDIDATES.get(surface)
    if not names or p.anchor != ANCHOR_HULL:
        return p
    table = anchors(spec, surface)
    cx, cy = center(p)
    name = min(names, key=lambda n: math.hypot(cx - table[n][0], cy - table[n][1]))
    bx, by = table[name]
    return replace(p, x=p.x - bx, y=p.y - by, anchor=name)

# ==========================================
# СЕРИАЛИЗАЦИЯ ОДНОЙ ДЕТАЛИ
# ==========================================

def part_to_dict(p):
    return {"k": p.kind, "s": p.surface, "a": p.anchor,
            "x": round(p.x, 4), "y": round(p.y, 4), "w": round(p.w, 4), "h": round(p.h, 4),
            "r": round(p.angle, 3), "m": p.mirror, "var": p.variant, "z": p.z}

def part_from_dict(d, surface):
    """Деталь из словаря или None. Неизвестный тип, чужая поверхность, неизвестный якорь, мусор
    в числах: пропуск. Числа подрезаются под границы типа."""
    if not isinstance(d, dict):
        return None
    kind = d.get("k")
    ptype = PART_TYPES.get(kind) if isinstance(kind, str) else None
    if ptype is None or surface not in ptype.surfaces or d.get("s", surface) != surface:
        return None
    anchor = d.get("a", ANCHOR_HULL)
    if anchor not in ANCHOR_NAMES[surface]:
        return None
    vals = [d.get(key, 0.0) for key in ("x", "y", "w", "h", "r")]
    if not all(_num(v) for v in vals):
        return None
    x, y, w, h, r = (float(v) for v in vals)
    var, z, mirror = d.get("var", 0), d.get("z"), d.get("m", False)
    return Part(
        kind=kind,
        x=round(_limit(x, -COORD_LIMIT_M, COORD_LIMIT_M), 4),
        y=round(_limit(y, -COORD_LIMIT_M, COORD_LIMIT_M), 4),
        w=0.0 if ptype.w_range is None else round(_limit(w, *ptype.w_range), 4),
        h=0.0 if ptype.h_range is None else round(_limit(h, *ptype.h_range), 4),
        angle=round(r % 360.0, 3),
        mirror=mirror if isinstance(mirror, bool) else False,
        variant=_limit(var, 0, VARIANT_MAX) if _int(var) else 0,
        z=_limit(z, 0, Z_MAX) if _int(z) else None,
        surface=surface, anchor=anchor)

# ==========================================
# ДИЗАЙН ЦЕЛИКОМ
# ==========================================

@dataclass(frozen=True)
class PartsDesign:
    """Ручные списки деталей по поверхностям. Имена полей совпадают со значениями SURFACE_*."""
    hull: Optional[tuple] = None
    turret: Optional[tuple] = None
    barrel: Optional[tuple] = None

    def get(self, surface):
        return getattr(self, surface)

    @property
    def is_auto(self):
        return self.hull is None and self.turret is None and self.barrel is None

    @property
    def key(self):
        """Число для ключей кэша спрайтов: None у авто-дизайна."""
        return None if self.is_auto else hash((self.hull, self.turret, self.barrel))

    def surface_key(self, surface):
        """Ключ кэша одной поверхности: None у авто-набора."""
        lst = self.get(surface)
        return None if lst is None else hash(lst)

    def with_parts(self, surface, parts):
        """Копия дизайна, где поверхность переведена в «Вручную» с этими деталями (None: обратно в «Авто»)."""
        return replace(self, **{surface: None if parts is None else tuple(parts)})

    def to_data(self):
        data = {"version": FORMAT_VERSION}
        for s in SURFACES:
            lst = self.get(s)
            data[s] = None if lst is None else [part_to_dict(p) for p in lst]
        return data

    @classmethod
    def from_data(cls, data):
        """Принимает None, словарь из файла или готовый PartsDesign. Мусор и версия новее
        нашей: «Авто». Битые детали пропускаются, остальные загружаются."""
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return AUTO_DESIGN
        version = data.get("version", 1)
        if not _int(version) or version > FORMAT_VERSION:
            return AUTO_DESIGN
        lists = {}
        for s in SURFACES:
            raw = data.get(s)
            if not isinstance(raw, list):
                lists[s] = None
                continue
            parsed = (part_from_dict(d, s) for d in raw[:LIMITS[s]])
            lists[s] = tuple(p for p in parsed if p is not None)
        return cls(**lists)

AUTO_DESIGN = PartsDesign()

def clean_design_data(data):
    """Словарь из файла -> проверенный словарь для session.values (или None, если всё «Авто»)."""
    design = PartsDesign.from_data(data)
    return None if design.is_auto else design.to_data()