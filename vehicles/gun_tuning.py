"""vehicles/gun_tuning.py — тюнинг орудия: номиналы по калибру, профили орудий, коридоры выбора, множитель перезарядки.
Чистые функции без pygame и без знания о танке: их берёт любая техника с орудием."""
from dataclasses import dataclass

from engine import clamp, lerp, round_to
from .gun_params import (
    CALIBER, GUN_DAMAGE_REF, GUN_PEN_REF,
    GUN_DAMAGE_RANGE, GUN_PEN_RANGE, GUN_DAMAGE_STEP, GUN_PEN_STEP,
    GUN_TUNE_RELOAD_A, GUN_TUNE_RELOAD_B,
)

_CAL = CALIBER
_REF_CAL = _CAL.default

# ---------- профиль орудия ----------
def _cal_t(cal):
    """Положение калибра в диапазоне 0..1 (диапазон калибров у ОБТ и ПТ-САУ общий)."""
    return clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)

@dataclass(frozen=True)
class GunProfile:
    """Во сколько раз орудие этого типа мощнее «базового» при минимальном и максимальном калибре.
    Между ними множитель растёт линейно: чем крупнее калибр, тем заметнее разница."""
    dmg_bonus: tuple = (1.0, 1.0)
    pen_bonus: tuple = (1.0, 1.0)
    speed_bonus: tuple = (1.0, 1.0)
    range_bonus: tuple = (1.0, 1.0)

    def dmg_mult(self, cal):
        return lerp(self.dmg_bonus[0], self.dmg_bonus[1], _cal_t(cal))

    def pen_mult(self, cal):
        return lerp(self.pen_bonus[0], self.pen_bonus[1], _cal_t(cal))

    def speed_mult(self, cal):
        return lerp(self.speed_bonus[0], self.speed_bonus[1], _cal_t(cal))

    def range_mult(self, cal):
        return lerp(self.range_bonus[0], self.range_bonus[1], _cal_t(cal))

MBT_GUN = GunProfile()
TD_GUN = GunProfile(dmg_bonus=(1.05, 1.30), pen_bonus=(1.03, 1.15),
                    speed_bonus=(1.0, 1.15), range_bonus=(1.0, 1.25))

# ---------- номиналы: зависят от калибра и профиля ----------
def nominal_damage(cal, profile=MBT_GUN):
    """Урон «по умолчанию» для калибра cal (центр коридора)."""
    return GUN_DAMAGE_REF * (cal / _REF_CAL) ** 2 * profile.dmg_mult(cal)

def nominal_pen(cal, profile=MBT_GUN):
    """Пробитие «по умолчанию» для калибра cal, мм (центр коридора)."""
    return GUN_PEN_REF * (cal / _REF_CAL) ** 0.8 * profile.pen_mult(cal)

# ---------- коридоры выбора ----------
def _corridor(nominal, ratios, step):
    lo = round_to(nominal * ratios[0], step)
    hi = round_to(nominal * ratios[1], step)
    return lo, max(hi, lo + step)

def damage_range(cal, profile=MBT_GUN):
    """Границы ползунка урона для калибра cal: (min, max)."""
    return _corridor(nominal_damage(cal, profile), GUN_DAMAGE_RANGE, GUN_DAMAGE_STEP)

def pen_range(cal, profile=MBT_GUN):
    """Границы ползунка пробития для калибра cal: (min, max)."""
    return _corridor(nominal_pen(cal, profile), GUN_PEN_RANGE, GUN_PEN_STEP)

def default_tuning(cal, profile=MBT_GUN):
    d = clamp(round_to(nominal_damage(cal, profile), GUN_DAMAGE_STEP), *damage_range(cal, profile))
    p = clamp(round_to(nominal_pen(cal, profile), GUN_PEN_STEP), *pen_range(cal, profile))
    return d, p

def remap(value, old_range, new_range, step=None):
    """Переносит значение из старого коридора в новый, сохраняя относительную позицию ползунка."""
    old_lo, old_hi = old_range
    new_lo, new_hi = new_range
    t = 0.5 if old_hi <= old_lo else clamp((value - old_lo) / (old_hi - old_lo), 0.0, 1.0)
    result = new_lo + (new_hi - new_lo) * t
    if step:
        result = clamp(round_to(result, step), new_lo, new_hi)
    return result

# ---------- перезарядка ----------
def reload_factor(dmg_k, pen_k):
    """Во сколько раз тюнинг удлиняет (>1) или укорачивает (<1) перезарядку."""
    return dmg_k ** GUN_TUNE_RELOAD_A * pen_k ** GUN_TUNE_RELOAD_B

# ---------- итог для GunSpec ----------
def resolve_tuning(cal, damage=None, penetration=None, profile=MBT_GUN):
    """Приводит выбор игрока к рабочим значениям.
    dmg_k и pen_k считаются от номинала СВОЕГО профиля, поэтому бонус ПТ-САУ
    на перезарядку не влияет (reload_factor его «не видит»)."""
    nom_d, nom_p = nominal_damage(cal, profile), nominal_pen(cal, profile)
    if damage is None:
        damage = nom_d
    else:
        lo, hi = damage_range(cal, profile)
        damage = clamp(float(damage), lo, hi)
    if penetration is None:
        penetration = nom_p
    else:
        lo, hi = pen_range(cal, profile)
        penetration = clamp(float(penetration), lo, hi)
    return damage, penetration, damage / nom_d, penetration / nom_p

def tuning_k_bounds():
    """Реальные крайние множители урона и пробития среди ВСЕХ калибров (для профиля ОБТ):
    ((dmg_min, dmg_max), (pen_min, pen_max)). Нужны модели цены танка."""
    cal = CALIBER
    dk, pk = [], []
    for c in range(int(cal.min), int(cal.max) + 1):
        d_lo, d_hi = damage_range(c)
        p_lo, p_hi = pen_range(c)
        nd, npn = nominal_damage(c), nominal_pen(c)
        dk.extend((d_lo / nd, d_hi / nd))
        pk.extend((p_lo / npn, p_hi / npn))
    return (min(dk), max(dk)), (min(pk), max(pk))