"""ai/roster/loadout.py — подбор значений ползунков архетипа под бюджет."""
from vehicles import (
    VEHICLE_TYPES, GUN_TUNE_PARAMS, FRONT_SCREEN, damage_range,
    pen_range, remap, nominal_damage, nominal_pen, raw_cost,
    MBT_GUN, default_length, effective_length, length_pen_k, length_cost_k
)

DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

BUDGET_TOLERANCE = 0.01      # цель подбора = бюджет * случайно от (1 - это) до (1 + это)
T_LIMIT = 3.0               # потолок «уровня» t
T_GROW = 1.5                 # во сколько раз расширяем уровень, пока цена не превысит цель
BISECT_STEPS = 14

def _values_at(arch, vtype, jitter, tune, screen, t, shift=0.0):
    """Значения всех ползунков на уровне t (t > 1 допустимо)."""
    out = {}
    for key, p in vtype.params.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        v = max(p.min, round(v / p.step) * p.step)
        cap = arch.caps.get(key)
        if cap is not None:
            v = max(p.min, min(v, cap))
        out[key] = v
    if vtype.bot_caliber_limits is not None:
        lo, hi = vtype.bot_caliber_limits(out)
        out["gun_caliber_mm"] = max(lo, min(out["gun_caliber_mm"], hi))
    if vtype.extra_values is not None:
        return vtype.extra_values(out, arch, tune, screen)

    # длина ствола
    cal = out["gun_caliber_mm"]
    length = effective_length(cal, round(default_length(cal) + shift))
    out["gun_length_cal"] = length

    # урон и пробитие
    t_dmg, t_pen = tune
    out["gun_damage"] = remap(t_dmg, (0.0, 1.0), damage_range(cal, vtype.gun_profile), DMG_STEP)
    out["gun_penetration"] = remap(t_pen, (0.0, 1.0), pen_range(cal, vtype.gun_profile, length), PEN_STEP)
    out["front_nose"] = arch.nose
    out["front_screen_mm"] = screen
    return out

def loadout_cost(values, vtype=None):
    """Неокруглённая цена сборки."""
    if vtype is not None and vtype.cost_fn is not None:
        return vtype.cost_fn(values)
    profile = vtype.gun_profile if vtype is not None else MBT_GUN
    cal = values["gun_caliber_mm"]
    length = values.get("gun_length_cal") or default_length(cal)
    front = values["front_armor_mm"] + values.get("front_screen_mm", 0.0)
    return raw_cost(cal, front, values["side_armor_mm"],
                    values["rear_armor_mm"], values["engine_power_hp"],
                    values["gun_damage"] / nominal_damage(cal, profile),
                    values["gun_penetration"] / nominal_pen(cal, profile) ,
                    profile.dmg_mult(cal), profile.pen_mult(cal), length_cost_k(length))

def fit_loadout(arch, budget, rng):
    """Значения ползунков архетипа под бюджет."""
    vtype = VEHICLE_TYPES[arch.kind]
    jitter = {k: 1.0 + rng.uniform(-arch.jitter, arch.jitter) for k in vtype.params}
    tune = (rng.uniform(*arch.damage_band), rng.uniform(*arch.pen_band))
    shift = rng.uniform(*arch.length_shift)

    lo_s, hi_s = arch.screen_mm
    if hi_s > lo_s:
        step = FRONT_SCREEN.step
        screen = lo_s + rng.randint(0, round((hi_s - lo_s) / step)) * step
    else:
        screen = lo_s

    target = budget * rng.uniform(1.0 - BUDGET_TOLERANCE, 1.0 + BUDGET_TOLERANCE)

    def at(t):
        return _values_at(arch, vtype, jitter, tune, screen, t, shift)

    # Расширяем уровень вверх, пока цена не перешагнёт цель (или не упрёмся в потолок)
    lo, hi = 0.0, 1.0
    while hi < T_LIMIT and loadout_cost(at(hi), vtype) <= target:
        lo, hi = hi, min(T_LIMIT, hi * T_GROW)
    if loadout_cost(at(hi), vtype) <= target:
        return at(hi)

    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2.0
        if loadout_cost(at(mid), vtype) <= target:
            lo = mid
        else:
            hi = mid
    return at(lo)