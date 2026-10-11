"""vehicles — техника. Сейчас только танк; остальные типы появятся рядом (vehicles/btr, ...).
Снаружи: from vehicles import Tank, TankSpec, TankRenderer, TANK_PARAMS"""
from .tank import (Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF, cost_for,
                   LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO)

__all__ = ["Tank", "TankSpec", "TankRenderer", "TANK_PARAMS", "COST_REF",
           "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO", "cost_for"]