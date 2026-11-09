"""vehicles/parts/render.py — рисование деталей одной полосы слоёв на готовом Pen."""
from .frame import PartPen
from .registry import PART_TYPES, z_of

def draw_parts(pen, parts, band, ctx):
    """Рисует детали полосы band = (от, до) по возрастанию z; при равном z порядок как в списке."""
    lo, hi = band
    todo = [(z_of(p), i, p) for i, p in enumerate(parts) if lo <= z_of(p) < hi]
    todo.sort(key=lambda t: (t[0], t[1]))
    for _, _, part in todo:
        ptype = PART_TYPES.get(part.kind)
        if ptype is not None:
            ptype.draw(PartPen(pen, part), part, ctx)