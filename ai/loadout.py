"""ai/loadout.py — подбор значений ползунков архетипа под бюджет."""
from engine import clamp
from vehicles import TANK_PARAMS, COST_REF, cost_for

BASE_BUDGET = COST_REF

def _values_at(arch, jitter, t):
    out = {}
    for key, p in TANK_PARAMS.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        out[key] = clamp(round(v / p.step) * p.step, p.min, p.max)
    return out

def _cost(values):
    return cost_for(values["gun_caliber_mm"], values["front_armor_mm"], values["side_armor_mm"],
                    values["rear_armor_mm"], values["engine_power_hp"])

def fit_loadout(arch, budget, rng):
    """Значения ползунков архетипа под бюджет. Разброс фиксируется ДО бисекции,
    иначе цена перестаёт быть монотонной по t."""
    jitter = {k: 1.0 + rng.uniform(-arch.jitter, arch.jitter) for k in TANK_PARAMS}

    if arch.t_anchor is not None and budget == BASE_BUDGET:
        return _values_at(arch, jitter, arch.t_anchor)       # ровно эталон

    top = _values_at(arch, jitter, 1.0)
    if _cost(top) <= budget:
        return top
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2.0
        if _cost(_values_at(arch, jitter, mid)) <= budget:
            lo = mid
        else:
            hi = mid
    return _values_at(arch, jitter, lo)