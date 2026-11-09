"""vehicles/td/casemate.py — геометрия рубки ПТ-САУ."""
from .params import TD_CASEMATE_AHEAD_M

CASEMATE_REACH = (1.9, 2.3, 2.8)   # сколько метров корпуса лежит ПОЗАДИ оси орудия, по уровням опоры
HULL_FRONT_MARGIN = 0.35           # рубка не заходит на лобовую плиту: её край + этот отступ
HULL_REAR_MARGIN = 0.10            # и не выходит за корму корпуса
CASEMATE_INSET = 0.28              # отступ верхней плиты рубки от её контура

def casemate_box(spec):
    """(ось орудия, передняя грань, задняя грань, полуширина спереди, полуширина сзади), метры корпуса."""
    layout = spec.layout
    axis = -layout.axis_fwd_m                      # ось орудия в координатах корпуса (перёд = -y)
    support = spec.SUPPORT
    g = spec.CASE_K
    front_limit = min(y for _, y in layout.front_plate) + HULL_FRONT_MARGIN
    rear_limit = max(y for _, y in layout.outline) - HULL_REAR_MARGIN
    front = max(axis - TD_CASEMATE_AHEAD_M, front_limit)
    rear = min(axis + CASEMATE_REACH[support] * g, rear_limit)
    rear = max(rear, front + 1.3)
    wf = 0.65 + 0.30 * g
    wr = 0.80 + 0.35 * g + (0.10 if support >= 2 else 0.0)
    return axis, front, rear, wf, wr