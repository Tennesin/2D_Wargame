"""tank/gun_tuning.py — тюнинг орудия: номиналы по калибру, коридоры выбора, множитель перезарядки.
Чистые функции без pygame и без знания о танке: их же сможет взять любая будущая техника с орудием."""
import math

from engine import clamp
from .params import (
    PARAMS, GUN_DAMAGE_REF, GUN_PEN_REF,
    GUN_DAMAGE_RANGE, GUN_PEN_RANGE, GUN_DAMAGE_STEP, GUN_PEN_STEP,
    GUN_TUNE_RELOAD_A, GUN_TUNE_RELOAD_B,
)

_REF_CAL = PARAMS["gun_caliber_mm"].default

def _round_to(value, step):
    """Округление до ближайшего кратного step (половина вверх)."""
    return math.floor(value / step + 0.5) * step

# ---------- номиналы: зависят ТОЛЬКО от калибра ----------
def nominal_damage(cal):
    """Урон «по умолчанию» для калибра cal (центр коридора)."""
    return GUN_DAMAGE_REF * (cal / _REF_CAL) ** 2

def nominal_pen(cal):
    """Пробитие «по умолчанию» для калибра cal, мм (центр коридора)."""
    return GUN_PEN_REF * (cal / _REF_CAL) ** 0.8

# ---------- коридоры выбора ----------
def _corridor(nominal, ratios, step):
    """(min, max), кратные step. Гарантируем, что max больше min хотя бы на один шаг."""
    lo = _round_to(nominal * ratios[0], step)
    hi = _round_to(nominal * ratios[1], step)
    return lo, max(hi, lo + step)

def damage_range(cal):
    """Границы ползунка урона для калибра cal: (min, max)."""
    return _corridor(nominal_damage(cal), GUN_DAMAGE_RANGE, GUN_DAMAGE_STEP)

def pen_range(cal):
    """Границы ползунка пробития для калибра cal: (min, max)."""
    return _corridor(nominal_pen(cal), GUN_PEN_RANGE, GUN_PEN_STEP)

def remap(value, old_range, new_range, step=None):
    """Переносит значение из старого коридора в новый, сохраняя относительную позицию ползунка.
    step: если задан, результат округляется до него (границы коридоров уже кратны шагу)."""
    old_lo, old_hi = old_range
    new_lo, new_hi = new_range
    t = 0.5 if old_hi <= old_lo else clamp((value - old_lo) / (old_hi - old_lo), 0.0, 1.0)
    result = new_lo + (new_hi - new_lo) * t
    if step:
        result = clamp(_round_to(result, step), new_lo, new_hi)
    return result

# ---------- перезарядка ----------
def reload_factor(dmg_k, pen_k):
    """Во сколько раз тюнинг удлиняет (>1) или укорачивает (<1) перезарядку."""
    return dmg_k ** GUN_TUNE_RELOAD_A * pen_k ** GUN_TUNE_RELOAD_B

# ---------- итог для GunSpec ----------
def resolve_tuning(cal, damage=None, penetration=None):
    """Приводит выбор игрока к рабочим значениям."""
    nom_d, nom_p = nominal_damage(cal), nominal_pen(cal)
    if damage is None:
        damage = nom_d
    else:
        lo, hi = damage_range(cal)
        damage = clamp(float(damage), lo, hi)
    if penetration is None:
        penetration = nom_p
    else:
        lo, hi = pen_range(cal)
        penetration = clamp(float(penetration), lo, hi)
    return damage, penetration, damage / nom_d, penetration / nom_p

def tuning_k_bounds():
    """Реальные крайние множители урона и пробития среди ВСЕХ калибров: ((dmg_min, dmg_max), (pen_min, pen_max)).
    Из-за округления до шага у мелких калибров они чуть шире номинальных коридоров 0.62..1.38 и 0.71..1.29."""
    cal = PARAMS["gun_caliber_mm"]
    dk, pk = [], []
    for c in range(int(cal.min), int(cal.max) + 1):
        d_lo, d_hi = damage_range(c)
        p_lo, p_hi = pen_range(c)
        nd, npn = nominal_damage(c), nominal_pen(c)
        dk.extend((d_lo / nd, d_hi / nd))
        pk.extend((p_lo / npn, p_hi / npn))
    return (min(dk), max(dk)), (min(pk), max(pk))