"""vehicles/spg/case.py — геометрия открытого боевого отделения САУ."""

CASE_FRONT_M = 0.45        # передняя стенка отделения впереди оси орудия
CASE_REACH_M = 1.65        # на сколько метров назад от оси уходит отделение (до масштаба CASE_K)
REAR_MARGIN_M = 0.45       # отделение не доходит до кормы корпуса: там плита и выхлоп
CASE_INSET_M = 0.24        # ширина светлой кромки стенок отделения

def spg_case_box(spec):
    """(ось орудия, перед, зад, полуширина спереди, полуширина сзади), метры корпуса."""
    layout = spec.layout
    axis = -layout.axis_fwd_m
    g = spec.CASE_K
    tail = max(y for _, y in layout.outline)
    front = axis - CASE_FRONT_M
    rear = min(axis + CASE_REACH_M * g, tail - REAR_MARGIN_M)
    rear = max(rear, front + 1.6)
    wf = 0.80 + 0.30 * g
    wr = wf + 0.18
    return axis, front, rear, wf, wr