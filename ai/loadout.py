"""ai/loadout.py — подбор значений ползунков архетипа под бюджет."""
from engine import clamp, VehicleKind
from vehicles import (VEHICLE_TYPES, GUN_TUNE_PARAMS, COST_REF, cost_for, FRONT_SCREEN,
                      damage_range, pen_range, remap, nominal_damage, nominal_pen,
                      caliber_range_for)

BASE_BUDGET = COST_REF
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

def _values_at(arch, vtype, jitter, tune, screen, t):
    """Значения всех ползунков на уровне t. tune = (положение урона, положение пробития), обе 0..1.
    screen: толщина лобовых экранов, выбранная заранее."""
    out = {}
    for key, p in vtype.params.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        out[key] = clamp(round(v / p.step) * p.step, p.min, p.max)

    # ограничение калибра по тяжести корпуса (только у ОБТ: у ПТ-САУ нет классов корпуса)
    if vtype.kind is VehicleKind.MBT:
        lo, hi = caliber_range_for(out["front_armor_mm"], out["side_armor_mm"],
                                   out["rear_armor_mm"], out["engine_power_hp"])
        out["gun_caliber_mm"] = clamp(out["gun_caliber_mm"], lo, hi)

    # урон и пробитие: то же относительное положение, но в коридоре ТЕКУЩЕГО калибра и профиля орудия
    cal = out["gun_caliber_mm"]
    t_dmg, t_pen = tune
    out["gun_damage"] = remap(t_dmg, (0.0, 1.0), damage_range(cal, vtype.gun_profile), DMG_STEP)
    out["gun_penetration"] = remap(t_pen, (0.0, 1.0), pen_range(cal, vtype.gun_profile), PEN_STEP)
    out["front_nose"] = arch.nose
    out["front_screen_mm"] = screen
    return out

def _cost(values):
    # Экран входит в цену как часть лба (так считает TankSpec._calc_economy).
    cal = values["gun_caliber_mm"]
    front = values["front_armor_mm"] + values.get("front_screen_mm", 0.0)
    return cost_for(cal, front, values["side_armor_mm"],
                    values["rear_armor_mm"], values["engine_power_hp"],
                    values["gun_damage"] / nominal_damage(cal),
                    values["gun_penetration"] / nominal_pen(cal))

def fit_loadout(arch, budget, rng):
    """Значения ползунков архетипа под бюджет. Разброс, тюнинг и экраны фиксируются ДО бисекции,
    иначе цена перестаёт быть монотонной по t."""
    vtype = VEHICLE_TYPES[arch.kind]
    jitter = {k: 1.0 + rng.uniform(-arch.jitter, arch.jitter) for k in vtype.params}
    tune = (rng.uniform(*arch.damage_band), rng.uniform(*arch.pen_band))

    lo_s, hi_s = arch.screen_mm
    if hi_s > lo_s:                          # случайная ступень из 15 / 30 / 45 (равные шансы)
        step = FRONT_SCREEN.step
        screen = lo_s + rng.randint(0, round((hi_s - lo_s) / step)) * step
    else:
        screen = lo_s                        # у остальных архетипов 0, генератор не трогаем

    top = _values_at(arch, vtype, jitter, tune, screen, 1.0)
    if _cost(top) <= budget:
        return top
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2.0
        if _cost(_values_at(arch, vtype, jitter, tune, screen, mid)) <= budget:
            lo = mid
        else:
            hi = mid
    return _values_at(arch, vtype, jitter, tune, screen, lo)