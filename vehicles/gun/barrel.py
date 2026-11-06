"""vehicles/gun/barrel.py — дизайн ствола: пределы длины (в калибрах) и толщины, видимая длина,
влияние длины на пробитие. Чистые функции без pygame и без знания о технике."""
from engine import clamp, lerp, round_to
from vehicles.gun.params import (
    CALIBER, REF_L_CAL, BARREL_VISIBLE_K, BARREL_THICK_REF_M, BARREL_THICK_EXP,
    BARREL_THICK_MIN_M, BARREL_THICK_MAX_M, BARREL_THICK_STEP_M,
    BARREL_LEN_AT_MIN_CAL, BARREL_LEN_AT_MAX_CAL,
    BARREL_THICK_LEN_EXP, BARREL_VIS_MAX_M, GUN_LENGTH_PEN_EXP,
    GUN_BARREL_MASS_SHARE, GUN_LENGTH_COST_EXP,
)

_REF_CAL = CALIBER.default
_REF_PHYS_M = _REF_CAL * REF_L_CAL / 1000.0 * BARREL_VISIBLE_K   # физическая длина эталона, м

def _cal_t(cal):
    return clamp((cal - CALIBER.min) / (CALIBER.max - CALIBER.min), 0.0, 1.0)

# ---------- длина в калибрах ----------
def length_range(cal):
    """Границы длины ствола в калибрах для калибра cal: (мин, макс)."""
    t = _cal_t(cal)
    return (round(lerp(BARREL_LEN_AT_MIN_CAL[0], BARREL_LEN_AT_MAX_CAL[0], t)),
            round(lerp(BARREL_LEN_AT_MIN_CAL[1], BARREL_LEN_AT_MAX_CAL[1], t)))

def default_length(cal):
    return float(clamp(REF_L_CAL, *length_range(cal)))

def resolve_length(cal, requested):
    """Выбор игрока, приведённый к коридору."""
    return clamp(float(requested), *length_range(cal))

def effective_length(cal, requested=None):
    """Итоговая длина ствола, кал.: выбор игрока (или авто = эталон), приведённый к коридору калибра.
    Единая точка входа: массы, спецификация и подбор ботов считают длину только через неё."""
    return resolve_length(cal, default_length(cal) if requested is None else requested)

def length_bounds():
    """Самая короткая и самая длинная длина ствола среди всех калибров (для калибровки цены)."""
    return (min(BARREL_LEN_AT_MIN_CAL[0], BARREL_LEN_AT_MAX_CAL[0]),
            max(BARREL_LEN_AT_MIN_CAL[1], BARREL_LEN_AT_MAX_CAL[1]))

def gun_mass_k(length_cal):
    """Множитель массы орудия от длины ствола. None и эталонная длина: 1.0."""
    if length_cal is None:
        return 1.0
    return 1.0 + GUN_BARREL_MASS_SHARE * (length_cal / REF_L_CAL - 1.0)

def length_cost_k(length_cal):
    """Множитель цены орудия от длины ствола (скорость и дальность стоят денег). None: 1.0."""
    if length_cal is None:
        return 1.0
    return (length_cal / REF_L_CAL) ** GUN_LENGTH_COST_EXP

# ---------- толщина ----------
def nominal_thickness(cal, length_cal):
    """Номинал толщины, м спрайта: растёт с калибром, убывает с длиной."""
    k = (REF_L_CAL / length_cal) ** BARREL_THICK_LEN_EXP
    return max(BARREL_THICK_MIN_M, BARREL_THICK_REF_M * (cal / _REF_CAL) ** BARREL_THICK_EXP * k)

def default_thickness(cal, length_cal):
    """Толщина ствола, м спрайта."""
    nom = clamp(nominal_thickness(cal, length_cal), BARREL_THICK_MIN_M, BARREL_THICK_MAX_M)
    return round(round_to(nom, BARREL_THICK_STEP_M), 3)

# ---------- видимая длина и пробитие ----------
def visual_length_m(cal, length_cal, ref_m):
    """Видимая длина ствола в мировых метрах: физическая (калибр × длина), нормированная так,
    чтобы эталон (125 мм, 44 кал.) давал ref_m, как раньше у данного типа техники."""
    physical = cal * length_cal / 1000.0 * BARREL_VISIBLE_K
    return min(physical * ref_m / _REF_PHYS_M, BARREL_VIS_MAX_M)

def length_pen_k(length_cal):
    """Множитель номинального пробития от длины. None (авто): 1.0, формулы не меняются."""
    if length_cal is None:
        return 1.0
    return (REF_L_CAL / length_cal) ** GUN_LENGTH_PEN_EXP