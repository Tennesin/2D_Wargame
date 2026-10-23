"""vehicles/cost.py — модель цены техники: индекс ценности -> цена.
Откалибрована по эталонному танку; ПТ-САУ и боты пользуются той же моделью."""
import itertools
import math

from engine import clamp, round_to
from vehicles.gun.params import GUN_TUNE_COST_D, GUN_TUNE_COST_P
from vehicles.gun.spec import turret_masses, REF_CAL, REF_POWER
from vehicles.gun.tuning import tuning_k_bounds
from .tank.params import (
    PARAMS, FIXED_MASS_T, COST_REF, COST_MIN, COST_MAX, COST_STEP, COST_ARMOR_ZONES, COST_PARTS,
)

_CAL = PARAMS["gun_caliber_mm"]
_FRONT = PARAMS["front_armor_mm"]
_SIDE = PARAMS["side_armor_mm"]
_REAR = PARAMS["rear_armor_mm"]
_POWER = PARAMS["engine_power_hp"]

_REF_HULL_MASS = FIXED_MASS_T + turret_masses(REF_CAL)[1]

def _cost_index(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Ценность машины относительно эталона (у эталона 1.0). Зависит только от входных параметров.
    dmg_k и pen_k: выбранные урон и пробитие относительно номинала калибра (1.0 = номинал)."""
    turret = turret_masses(cal)[1]
    zf, zs, zr = COST_ARMOR_ZONES
    levels = {
        "armor":  (zf * front / _FRONT.default + zs * side / _SIDE.default
                   + zr * rear / _REAR.default) / (zf + zs + zr),
        "hull":   (FIXED_MASS_T + turret) / _REF_HULL_MASS,
        "engine": power / REF_POWER,
        "gun":    cal / REF_CAL * dmg_k ** GUN_TUNE_COST_D * pen_k ** GUN_TUNE_COST_P,
    }
    return sum(weight * levels[name] ** power_k for name, (weight, power_k) in COST_PARTS.items())

# Самая дешёвая и самая дорогая возможные машины (все ползунки в минимуме или в максимуме)
_DK, _PK = tuning_k_bounds()
_indexes = [_cost_index(*corner) for corner in itertools.product(
    *((p.min, p.max) for p in (_CAL, _FRONT, _SIDE, _REAR, _POWER)), _DK, _PK)]
INDEX_MIN, INDEX_MAX = min(_indexes), max(_indexes)
# Степени подобраны так, чтобы эталон стоил COST_REF, самая дешёвая машина COST_MIN, самая дорогая COST_MAX.
COST_EXP_LOW = math.log(COST_MIN / COST_REF) / math.log(INDEX_MIN)
COST_EXP_HIGH = math.log(COST_MAX / COST_REF) / math.log(INDEX_MAX)

def _price(index):
    return COST_REF * index ** (COST_EXP_LOW if index < 1.0 else COST_EXP_HIGH)

def raw_cost(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Цена до округления."""
    return _price(_cost_index(cal, front, side, rear, power, dmg_k, pen_k))

def round_cost(raw):
    """Округление цены до шага и в допустимых границах."""
    return clamp(round_to(raw, COST_STEP), COST_MIN, COST_MAX)

def cost_for(cal, front, side, rear, power, dmg_k=1.0, pen_k=1.0):
    """Цена машины по входным параметрам без полного расчёта спецификации."""
    return round_cost(raw_cost(cal, front, side, rear, power, dmg_k, pen_k))