"""vehicles/td/rules.py — правила ПТ-САУ: допустимый калибр по броне."""
from engine import clamp, lerp
from vehicles.gun.params import CALIBER
from .params import (TD_PARAMS, TD_FRONT_AREA_M2, TD_SIDE_AREA_M2, TD_REAR_AREA_M2,
                     TD_CAL_MIN_HEAVY, TD_CAL_MIN_FULL_INDEX,
                     TD_CAL_MAX_LIGHT, TD_CAL_MAX_FULL_INDEX)

_FRONT = TD_PARAMS["front_armor_mm"]
_SIDE = TD_PARAMS["side_armor_mm"]
_REAR = TD_PARAMS["rear_armor_mm"]

_IDX_MIN = (TD_FRONT_AREA_M2 * _FRONT.min + TD_SIDE_AREA_M2 * _SIDE.min + TD_REAR_AREA_M2 * _REAR.min)
_IDX_MAX = (TD_FRONT_AREA_M2 * _FRONT.max + TD_SIDE_AREA_M2 * _SIDE.max + TD_REAR_AREA_M2 * _REAR.max)

def td_armor_index(front, side, rear):
    """Индекс брони 0..1. У ботов значения могут быть выше границ ползунков: индекс просто упирается в 1."""
    mass = TD_FRONT_AREA_M2 * front + TD_SIDE_AREA_M2 * side + TD_REAR_AREA_M2 * rear
    return clamp((mass - _IDX_MIN) / (_IDX_MAX - _IDX_MIN), 0.0, 1.0)

def td_caliber_limits(front, side, rear):
    """(мин, макс) калибра, мм, для ПТ-САУ с такой бронёй."""
    idx = td_armor_index(front, side, rear)
    lo = lerp(CALIBER.min, TD_CAL_MIN_HEAVY, clamp(idx / TD_CAL_MIN_FULL_INDEX, 0.0, 1.0))
    hi = lerp(TD_CAL_MAX_LIGHT, CALIBER.max, clamp(idx / TD_CAL_MAX_FULL_INDEX, 0.0, 1.0))
    return round(lo), round(hi)