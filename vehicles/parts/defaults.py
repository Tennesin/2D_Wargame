"""vehicles/parts/defaults.py — авто-набор деталей."""
import math

from vehicles.chassis.hull_noses import PIKE_BAND_M
from vehicles.chassis.hulls import NOSE_PIKE, NOSE_WEDGE, HULL_STYLE_FRONT_ENGINE
from vehicles.gun.params import BARREL_HIDDEN_M, BARREL_LEN_STEP_M, BARREL_THICK_STEP_M
from .design import PartsDesign, resolve, anchor_part
from vehicles.render.pen import outline_x_at
from .library import SEAM_FRACS
from .model import SURFACE_HULL, SURFACE_TURRET, SURFACE_BARREL, Part

_BUILDERS = {}                      # (вид техники, поверхность) -> функция(spec, look, emblem) -> список Part

def default_builder(kind, surface):
    def register(fn):
        _BUILDERS[(kind, surface)] = fn
        return fn
    return register

def default_parts(kind, spec, surface, look=None, emblem=""):
    """Авто-набор деталей поверхности."""
    fn = _BUILDERS.get((kind, surface))
    if fn is None:
        return ()
    return tuple(fn(spec, spec.LOOK if look is None else look, emblem))

def parts_for(kind, spec, surface, look=None, emblem=""):
    """Какие детали рисовать."""
    design = getattr(spec, "parts_design", None)
    manual = None if design is None else design.get(surface)
    if manual is not None:
        return resolve(manual, spec, surface)
    return default_parts(kind, spec, surface, look, emblem)

def freeze_auto(kind, spec, emblem=""):
    """«Заморозить авто-набор»."""
    look = spec.LOOK
    length = round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M) * BARREL_LEN_STEP_M     # как в рендерере
    thick = round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M) * BARREL_THICK_STEP_M

    def anchored(parts, surface):
        return tuple(anchor_part(p, spec, surface) for p in parts)

    turret = None
    if kind == "mbt":
        turret = anchored(default_parts(kind, spec, SURFACE_TURRET, look, emblem), SURFACE_TURRET)
    return PartsDesign(
        hull=anchored(default_parts(kind, spec, SURFACE_HULL, look), SURFACE_HULL),
        turret=turret,
        barrel=anchored(barrel_parts(length, thick, look), SURFACE_BARREL))

def barrel_parts(length_m, thick_m, look):
    """Детали ствола."""
    half = (length_m + BARREL_HIDDEN_M) / 2.0
    s = SURFACE_BARREL
    parts = [
        Part("ejector", x=-(thick_m + 0.08) / 2.0, y=-half + 0.35 * length_m,
             w=thick_m + 0.08, h=0.30, surface=s),
        Part("muzzle_band", x=-(thick_m + 0.06) / 2.0, y=-half,
             w=thick_m + 0.06, h=0.22, surface=s),
    ]
    if look.gun > 0:                                    # дульный тормоз: шире ствола
        bw = thick_m + (0.14 if look.gun == 1 else 0.22)
        parts.append(Part("muzzle_brake", x=-bw / 2.0, y=-half + 0.25, w=bw, h=0.40, surface=s))
    return tuple(parts)

def barrel_parts_for(spec, length_m, thick_m, look):
    """Детали ствола для рендерера."""
    design = getattr(spec, "parts_design", None)
    manual = None if design is None else design.get(SURFACE_BARREL)
    if manual is not None:
        return resolve(manual, spec, SURFACE_BARREL)
    return barrel_parts(length_m, thick_m, look)

# ==========================================
# ОБЩИЕ ПОМОЩНИКИ
# ==========================================

def _seams(layout):
    """Поперечные швы палубы (до накладной брони)."""
    parts = []
    dx, dy, dw, dh = layout.deck_rect
    for t in SEAM_FRACS:
        y = dy + dh * t
        lo, hi = outline_x_at(layout.outline, y)
        if lo is None:
            continue
        x0, x1 = lo + 0.06, hi - 0.06
        parts.append(Part("seam", x=x0, y=y, w=x1 - x0))
    return parts

def _exhaust(layout, look):
    """Выхлопные патрубки: уровень от ползунков."""
    if look.speed <= 0:
        return []
    r = 0.13 if look.speed == 1 else 0.17
    return [Part("exhaust", x=x, y=layout.exhaust_y, w=r) for x in layout.exhaust_xs]

def _antenna(x0, y0, x1, y1, r, surface=SURFACE_HULL):
    """Антенна от основания (x0, y0) к концу (x1, y1). Тип хранит длину и поворот, поэтому
    пересчитываем: штырь по умолчанию идёт к корме (+y), поворот по часовой."""
    dx, dy = x1 - x0, y1 - y0
    return Part("antenna", x=x0, y=y0, w=r, h=math.hypot(dx, dy),
                angle=math.degrees(math.atan2(-dx, dy)), surface=surface)

def _fender_gear(layout):
    """Ящики ЗИП и ручка на левом крыле, трос и скобы на правом (ПТ-САУ и САУ). Рисуются сразу после
    подкрылков, до бортовых экранов, поэтому z = 10 (полоса BAND_FENDER)."""
    if len(layout.fender_rects) < 2:
        return []
    (rfx, _, rfw, _), (lfx, _, lfw, _) = layout.fender_rects
    z = 10
    parts = [
        Part("toolbox", x=lfx, y=0.45, w=lfw, h=0.95, z=z),
        Part("toolbox", x=lfx, y=-1.75, w=lfw, h=0.55, z=z),
        Part("handle", x=lfx + lfw / 2.0, y=0.60, h=0.70, z=z),
        Part("cable", x=rfx + rfw / 2.0, y=-1.85, h=4.20, z=z),
    ]
    parts += [Part("clamp", x=rfx + 0.05, y=cy, w=0.12, h=0.14, z=z) for cy in (-1.3, 0.2, 1.7)]
    return parts

# ==========================================
# ОБТ
# ==========================================

@default_builder("mbt", SURFACE_HULL)
def _mbt_hull(spec, look, emblem=""):
    layout = spec.layout
    parts = list(_seams(layout))                        # поперечные швы палубы (до накладной брони)

    front_engine = layout.hull_style == HULL_STYLE_FRONT_ENGINE
    if front_engine:
        # моторная крышка носа: от начала палубы до передней кромки башни
        reach = layout.turret_front_m * layout.turret_k * layout.turret_scale_range[1]
        y_end = -layout.axis_fwd_m - reach
        if layout.nose == NOSE_PIKE:
            lead = PIKE_BAND_M + 0.10
        elif layout.nose == NOSE_WEDGE:
            lead = 0.20
        else:
            lead = 0.25
        half_w = layout.deck_rect[2] / 2.0 - 0.30
        y0 = layout.deck_rect[1] + lead
        free = y_end - 0.15 - y0
        if free >= 0.6:
            parts.append(Part("engine_cover", x=-half_w, y=y0, w=2.0 * half_w, h=free))

        # ящики ЗИП слева и трос справа лежат на бортовых экранах
        sy0, sy1, sw = layout.skirt_levels[0]
        cx = layout.skirt_outer_x - sw / 2.0
        span = sy1 - sy0
        parts.append(Part("toolbox", x=-cx - 0.15, y=sy0 + span * 0.50, w=0.30, h=0.95))
        parts.append(Part("toolbox", x=-cx - 0.15, y=sy0 + span * 0.20, w=0.30, h=0.60))
        parts.append(Part("cable", x=cx, y=sy0 + 0.5, h=(sy1 - 0.5) - (sy0 + 0.5)))
    else:
        # люк механика и решётка МТО позади башни
        hx, hy, hr = layout.hatch
        hy = max(hy, layout.deck_rect[1] + hr + 0.12)
        parts.append(Part("hatch", x=hx, y=hy, w=hr))
        gx, gy, gw, gh = layout.grill_rect
        parts.append(Part("grill", x=gx, y=gy, w=gw, h=gh))

    rx, ry, rw, rh = layout.rear_plate
    parts.append(Part("plate", x=rx, y=ry, w=rw, h=rh))
    parts += _exhaust(layout, look)
    return parts

@default_builder("mbt", SURFACE_TURRET)
def _mbt_turret(spec, look, emblem=""):
    """Детали башни по форме: шеврон, люки, швы крыши, антенна."""
    style = spec.layout.turret_style
    s = SURFACE_TURRET
    chevron = emblem == "chevron"
    parts = []
    if style == "oval":                                 # лёгкий корпус
        if chevron:
            parts.append(Part("chevron", x=0.0, y=0.25, w=0.85, surface=s))
        parts.append(Part("turret_hatch", x=0.45, y=0.55, w=0.32, h=0.23, surface=s))
        if look.speed > 0:
            parts.append(_antenna(-0.75, 0.90, -0.90, 1.75, 0.09, s))
    elif style == "slab":                               # тяжёлый корпус
        for sy in (0.0, 1.0):
            parts.append(Part("roof_seam", x=-0.95, y=sy, w=1.90, surface=s))
        if chevron:
            parts.append(Part("chevron", x=0.0, y=-0.05, w=0.9, surface=s))
        parts.append(Part("turret_hatch", x=0.62, y=0.45, w=0.36, h=0.26, surface=s))
        parts.append(Part("loader_hatch", x=-0.62, y=0.62, w=0.26, surface=s))
        if look.speed > 0:
            parts.append(_antenna(-0.80, 0.85, -0.92, 1.30, 0.09, s))
    else:                                               # hex: средний корпус
        if chevron:
            parts.append(Part("chevron", x=0.0, y=0.0, w=1.0, surface=s))
        parts.append(Part("turret_hatch", x=0.42, y=0.30, w=0.42, h=0.32, surface=s))
        if look.speed > 0:
            parts.append(_antenna(-0.75, 1.0, -0.95, 1.95, 0.10, s))
    return parts

# ==========================================
# ПТ-САУ
# ==========================================

@default_builder("td", SURFACE_HULL)
def _td_hull(spec, look, emblem=""):
    from vehicles.td.casemate import casemate_box, CASEMATE_INSET     # внутри функции: иначе круговой импорт
    layout = spec.layout
    axis, front, rear, wf, wr = casemate_box(spec)
    g = spec.CASE_K

    parts = _fender_gear(layout) + _seams(layout)

    # --- до рубки (полоса BAND_COVER) ---
    if spec.SUPPORT == 0 and rear < 2.0:                # моторная часть позади рубки
        gy = rear + 0.2
        gh = 2.75 - gy
        parts.append(Part("vent_grille", x=-0.95, y=gy, w=1.90, h=gh, variant=1 if gh >= 1.7 else 0))
        parts.append(Part("plate", x=-0.95, y=2.50, w=1.90, h=0.25, z=46))   # кормовая планка
    lead = PIKE_BAND_M + 0.10 if layout.nose == NOSE_PIKE else 0.45
    y0 = layout.deck_rect[1] + lead
    free = front - 0.15 - y0
    if free >= 0.9:
        parts.append(Part("engine_cover", x=-1.05, y=y0, w=2.10, h=free))

    # --- после рубки (полоса BAND_TOP): крыша ---
    seam_in = wr - CASEMATE_INSET
    for sy in (front + 1.15, rear - 1.05):              # швы между листами
        if front + 0.9 < sy < rear - 0.5:
            parts.append(Part("roof_seam", x=-seam_in, y=sy, w=2.0 * seam_in, z=60))
    half = math.radians(spec.TURRET_ARC_DEG / 2.0)
    lb = min(1.0, rear - 0.25 - axis)                   # длина лотка назад от оси
    t = lb * math.tan(half)                             # на сколько он расширяется к корме
    parts.append(Part("breech_tray", x=0.0, y=axis, w=0.64 + 2.0 * t, h=lb))
    ew = 0.55 + 0.15 * g                                # амбразура: орудие смотрит из передней грани
    parts.append(Part("embrasure", x=0.0, y=front, w=2.0 * ew, h=0.55))
    for sx in (-1, 1):                                  # перископы по углам передней части
        parts.append(Part("periscope", x=sx * 0.62 - 0.15, y=front + 0.62, w=0.30, h=0.10))
    parts.append(Part("dome", x=0.72, y=axis + 0.90, w=0.26, h=0.15))
    parts.append(Part("roof_hatch", x=-0.92, y=axis + 0.72, w=0.42, h=0.40))
    if rear - 0.62 >= axis + 1.0:                       # вентрешётка (только если не под казёнником)
        parts.append(Part("vent", x=-0.35, y=rear - 0.62, w=0.70, h=0.34))
    if look.speed > 0:
        ay = axis + 0.95
        parts.append(_antenna(-0.80, ay, -0.95, min(ay + 0.6, rear - 0.1), 0.09))
    parts += _exhaust(layout, look)
    return parts

# ==========================================
# САУ
# ==========================================

@default_builder("spg", SURFACE_HULL)
def _spg_hull(spec, look, emblem=""):
    from vehicles.spg.case import spg_case_box, CASE_INSET_M          # внутри функции: иначе круговой импорт
    layout = spec.layout
    axis, front, rear, wf, wr = spg_case_box(spec)

    parts = _fender_gear(layout) + _seams(layout)

    # --- до боевого отделения (полоса BAND_COVER) ---
    y0 = layout.deck_rect[1] + 0.45
    free = front - 0.15 - y0
    if free >= 0.9:
        parts.append(Part("engine_cover", x=-1.05, y=y0, w=2.10, h=free))
    rx, ry, rw, rh = layout.rear_plate
    parts.append(Part("plate", x=rx, y=ry, w=rw, h=rh, z=55))

    # --- внутри и позади отделения (полоса BAND_TOP) ---
    cy0 = rear - CASE_INSET_M - 0.55                    # ящики у задней стенки
    for cx in (-0.62, 0.02):
        parts.append(Part("ammo_crate", x=cx, y=cy0, w=0.58, h=0.45))
    if look.speed > 0:
        parts.append(_antenna(-wr + 0.12, rear - 0.9, -wr + 0.05, rear - 0.2, 0.08))
    parts += _exhaust(layout, look)
    return parts