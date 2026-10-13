"""vehicles — техника. Базовое шасси Vehicle, техника с орудием GunVehicle и конкретные типы:
танк (tank) и ПТ-САУ (td). Новые типы добавляются рядом и регистрируются в registry.py.
Снаружи: from vehicles import Vehicle, Tank, TankSpec, TankRenderer, TANK_PARAMS, make_vehicle, ..."""
from .base import Vehicle
from .gun_vehicle import GunVehicle
from .tank import (Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF, cost_for,
                   LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO,
                   GUN_TUNE_PARAMS, damage_range, pen_range, remap,
                   nominal_damage, nominal_pen, GunProfile, MBT_GUN, TD_GUN, default_tuning)
from .td import TDSpec, TankDestroyer, TDRenderer, TD_PARAMS
from .registry import VehicleType, VEHICLE_TYPES, RENDERERS, make_vehicle

__all__ = ["Vehicle", "GunVehicle", "Tank", "TankSpec", "TankRenderer", "TANK_PARAMS", "COST_REF",
           "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO", "cost_for",
           "GUN_TUNE_PARAMS", "damage_range", "pen_range", "remap",
           "nominal_damage", "nominal_pen", "GunProfile", "MBT_GUN", "TD_GUN", "default_tuning",
           "TDSpec", "TankDestroyer", "TDRenderer", "TD_PARAMS",
           "VehicleType", "VEHICLE_TYPES", "RENDERERS", "make_vehicle"]