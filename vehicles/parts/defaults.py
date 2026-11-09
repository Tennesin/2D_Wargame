"""vehicles/parts/defaults.py — авто-набор деталей."""
from vehicles.chassis.hull_noses import PIKE_BAND_M
from vehicles.chassis.hulls import NOSE_PIKE, NOSE_WEDGE, HULL_STYLE_FRONT_ENGINE
from vehicles.render.pen import outline_x_at
from .library import SEAM_FRACS
from .model import SURFACE_HULL, Part

_BUILDERS = {}                      # (вид техники, поверхность) -> функция(spec, look) -> список Part

def default_builder(kind, surface):
    def register(fn):
        _BUILDERS[(kind, surface)] = fn
        return fn
    return register

def default_parts(kind, spec, surface, look=None):
    """Авто-набор деталей поверхности. kind: ключ вида техники ("mbt", позже "td", "spg")."""
    fn = _BUILDERS.get((kind, surface))
    if fn is None:
        return ()
    return tuple(fn(spec, spec.LOOK if look is None else look))

def parts_for(kind, spec, surface, look=None):
    """Какие детали рисовать. Этап 1: всегда авто-набор. В этапе 2 здесь появится выбор «Авто / Вручную»."""
    return default_parts(kind, spec, surface, look)

@default_builder("mbt", SURFACE_HULL)
def _mbt_hull(spec, look):
    layout = spec.layout
    parts = []

    # поперечные швы палубы (до накладной брони)
    dx, dy, dw, dh = layout.deck_rect
    for t in SEAM_FRACS:
        y = dy + dh * t
        lo, hi = outline_x_at(layout.outline, y)
        if lo is None:
            continue
        x0, x1 = lo + 0.06, hi - 0.06
        parts.append(Part("seam", x=x0, y=y, w=x1 - x0))

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

    if look.speed > 0:                                  # выхлоп: уровень от ползунков
        r = 0.13 if look.speed == 1 else 0.17
        for x in layout.exhaust_xs:
            parts.append(Part("exhaust", x=x, y=layout.exhaust_y, w=r))
    return parts