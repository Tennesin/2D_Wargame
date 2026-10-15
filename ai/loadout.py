"""ai/loadout.py — подбор значений ползунков архетипа под бюджет."""
from engine import clamp
from vehicles import (VEHICLE_TYPES, GUN_TUNE_PARAMS, COST_REF, cost_for,
                      damage_range, pen_range, remap, nominal_damage, nominal_pen)

BASE_BUDGET = COST_REF
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

def _values_at(arch, vtype, jitter, tune, t):
    """Значения всех ползунков на уровне t. tune = (положение урона, положение пробития), обе 0..1."""
    out = {}
    for key, p in vtype.params.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        out[key] = clamp(round(v / p.step) * p.step, p.min, p.max)

    # урон и пробитие: то же относительное положение, но в коридоре ТЕКУЩЕГО калибра и профиля орудия
    cal = out["gun_caliber_mm"]
    t_dmg, t_pen = tune
    out["gun_damage"] = remap(t_dmg, (0.0, 1.0), damage_range(cal, vtype.gun_profile), DMG_STEP)
    out["gun_penetration"] = remap(t_pen, (0.0, 1.0), pen_range(cal, vtype.gun_profile), PEN_STEP)
    return out

def _cost(values):
    # Для ПТ-САУ это тоже верно: TDSpec считает цену как damage_k * dmg_mult профиля,
    # что равно урону, делённому на номинал ОБТ (профиль по умолчанию).
    cal = values["gun_caliber_mm"]
    return cost_for(cal, values["front_armor_mm"], values["side_armor_mm"],
                    values["rear_armor_mm"], values["engine_power_hp"],
                    values["gun_damage"] / nominal_damage(cal),
                    values["gun_penetration"] / nominal_pen(cal))

def fit_loadout(arch, budget, rng):
    """Значения ползунков архетипа под бюджет. Разброс и тюнинг фиксируются ДО бисекции,
    иначе цена перестаёт быть монотонной по t."""
    vtype = VEHICLE_TYPES[arch.kind]
    jitter = {k: 1.0 + rng.uniform(-arch.jitter, arch.jitter) for k in vtype.params}
    tune = (rng.uniform(*arch.damage_band), rng.uniform(*arch.pen_band))

    top = _values_at(arch, vtype, jitter, tune, 1.0)
    if _cost(top) <= budget:
        return top
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2.0
        if _cost(_values_at(arch, vtype, jitter, tune, mid)) <= budget:
            lo = mid
        else:
            hi = mid
    return _values_at(arch, vtype, jitter, tune, lo)