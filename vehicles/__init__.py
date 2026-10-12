"""vehicles — техника. Базовое шасси Vehicle и конкретные типы (сейчас только танк; остальные
появятся рядом: vehicles/btr, vehicles/td, ...).
Снаружи: from vehicles import Vehicle, Tank, TankSpec, TankRenderer, TANK_PARAMS"""
from .base import Vehicle
from .tank import (Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF, cost_for,
                   LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO,
                   GUN_TUNE_PARAMS, damage_range, pen_range, remap,
                   nominal_damage, nominal_pen)

__all__ = ["Vehicle", "Tank", "TankSpec", "TankRenderer", "TANK_PARAMS", "COST_REF",
           "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO", "cost_for",
           "GUN_TUNE_PARAMS", "damage_range", "pen_range", "remap",
           "nominal_damage", "nominal_pen"]