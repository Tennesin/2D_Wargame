"""ai/loadout.py — подбор значений ползунков архетипа под бюджет."""
from engine import clamp
from vehicles import TankSpec, TANK_PARAMS

BASE_BUDGET = 15000     # = COST_REF в vehicles/tank/params.py

def _values_at(arch, jitter, t):
    out = {}
    for key, p in TANK_PARAMS.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        out[key] = clamp(round(v / p.step) * p.step, p.min, p.max)
    return out

def _cost(values):
    return TankSpec.from_values(values).cost

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

def print_loadout_table(budgets=(5000, 15000, 25000, 35000)):
    """Проверка архетипов. Запуск из корня проекта:
    python -c "from ai.loadout import print_loadout_table; print_loadout_table()" """
    import random
    from .archetypes import ARCHETYPES
    rng = random.Random(1)
    print(f"{'архетип':<12}{'бюджет':>7}{'калибр':>8}{'лоб':>6}{'борт':>6}{'корма':>7}{'л.с.':>7}{'цена':>8}")
    for arch in ARCHETYPES.values():
        for b in budgets:
            v = fit_loadout(arch, b, rng)
            print(f"{arch.name:<12}{b:>7}{v['gun_caliber_mm']:>8.0f}{v['front_armor_mm']:>6.0f}"
                  f"{v['side_armor_mm']:>6.0f}{v['rear_armor_mm']:>7.0f}"
                  f"{v['engine_power_hp']:>7.0f}{_cost(v):>8}")