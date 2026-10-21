"""ai/loadout.py — подбор значений ползунков архетипа под бюджет.
Для ботов верхние границы ползунков и ограничение калибра по классу корпуса не действуют:
единственный предел — бюджет (плюс технический потолок T_LIMIT от абсурда)."""
from vehicles import (VEHICLE_TYPES, GUN_TUNE_PARAMS, COST_REF, FRONT_SCREEN,
                      damage_range, pen_range, remap, nominal_damage, nominal_pen, raw_cost)

BASE_BUDGET = COST_REF       # временно: нужен старому спавнеру, на шаге 3 уберём
DMG_STEP = GUN_TUNE_PARAMS["gun_damage"].step
PEN_STEP = GUN_TUNE_PARAMS["gun_penetration"].step

BUDGET_TOLERANCE = 0.01      # цель подбора = бюджет * случайно от (1 - это) до (1 + это)
T_LIMIT = 3.0               # потолок «уровня» t
T_GROW = 1.5                 # во сколько раз расширяем уровень, пока цена не превысит цель
BISECT_STEPS = 14

def _values_at(arch, vtype, jitter, tune, screen, t):
    """Значения всех ползунков на уровне t (t > 1 допустимо). tune = (положение урона, положение
    пробития), обе 0..1. screen: толщина лобовых экранов, выбранная заранее."""
    out = {}
    for key, p in vtype.params.items():
        w = min(1.0, arch.weights[key] * jitter[key])
        v = p.min + (p.max - p.min) * w * t
        out[key] = max(p.min, round(v / p.step) * p.step)      # только нижняя граница

    # урон и пробитие: то же относительное положение, но в коридоре ТЕКУЩЕГО калибра и профиля орудия
    cal = out["gun_caliber_mm"]
    t_dmg, t_pen = tune
    out["gun_damage"] = remap(t_dmg, (0.0, 1.0), damage_range(cal, vtype.gun_profile), DMG_STEP)
    out["gun_penetration"] = remap(t_pen, (0.0, 1.0), pen_range(cal, vtype.gun_profile), PEN_STEP)
    out["front_nose"] = arch.nose
    out["front_screen_mm"] = screen
    return out

def loadout_cost(values):
    """Неокруглённая цена сборки. Экран входит в цену как часть лба (так считает спецификация)."""
    cal = values["gun_caliber_mm"]
    front = values["front_armor_mm"] + values.get("front_screen_mm", 0.0)
    return raw_cost(cal, front, values["side_armor_mm"],
                    values["rear_armor_mm"], values["engine_power_hp"],
                    values["gun_damage"] / nominal_damage(cal),
                    values["gun_penetration"] / nominal_pen(cal))

def fit_loadout(arch, budget, rng):
    """Значения ползунков архетипа под бюджет (цена попадает в бюджет с точностью около ±1-2%).
    Разброс, тюнинг и экраны фиксируются ДО поиска, иначе цена перестаёт быть монотонной по t.
    Если даже самая дешёвая сборка дороже бюджета, возвращается она (ниже минимума не падаем)."""
    vtype = VEHICLE_TYPES[arch.kind]
    jitter = {k: 1.0 + rng.uniform(-arch.jitter, arch.jitter) for k in vtype.params}
    tune = (rng.uniform(*arch.damage_band), rng.uniform(*arch.pen_band))

    lo_s, hi_s = arch.screen_mm
    if hi_s > lo_s:                          # случайная ступень из 15 / 30 / 45 (равные шансы)
        step = FRONT_SCREEN.step
        screen = lo_s + rng.randint(0, round((hi_s - lo_s) / step)) * step
    else:
        screen = lo_s

    target = budget * rng.uniform(1.0 - BUDGET_TOLERANCE, 1.0 + BUDGET_TOLERANCE)

    def at(t):
        return _values_at(arch, vtype, jitter, tune, screen, t)

    # 1. Расширяем уровень вверх, пока цена не перешагнёт цель (или не упрёмся в потолок)
    lo, hi = 0.0, 1.0
    while hi < T_LIMIT and loadout_cost(at(hi)) <= target:
        lo, hi = hi, min(T_LIMIT, hi * T_GROW)
    if loadout_cost(at(hi)) <= target:
        return at(hi)                        # бюджет больше, чем можно потратить до потолка

    # 2. Бисекция внутри [lo, hi]: берём самую дорогую сборку, не превышающую цель
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2.0
        if loadout_cost(at(mid)) <= target:
            lo = mid
        else:
            hi = mid
    return at(lo)