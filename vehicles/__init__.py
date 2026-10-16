"""vehicles — техника. Базовое шасси Vehicle, техника с орудием GunVehicle и конкретные типы:
танк (tank) и ПТ-САУ (td). Новые типы добавляются рядом и регистрируются в registry.py.
Снаружи: from vehicles import Vehicle, Tank, TankSpec, TankRenderer, TANK_PARAMS, make_vehicle, ..."""
from .base import Vehicle
from .gun_vehicle import GunVehicle
from .gun_params import GUN_TUNE_PARAMS
from .chassis_params import FRONT_SCREEN
from .gun_tuning import (damage_range, pen_range, remap, nominal_damage, nominal_pen,
                         GunProfile, MBT_GUN, TD_GUN, default_tuning)
from .ammo import AmmoType, AMMO_TYPES, AMMO_ORDER, ammo_stats
from .tank import (Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF, cost_for,
                   LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO)
from .td import TDSpec, TankDestroyer, TDRenderer, TD_PARAMS, gun_arc_deg
from .registry import VehicleType, VEHICLE_TYPES, RENDERERS, make_vehicle
from .running_gear import RunningGear, TRACKS, TRACK_SIDES
from .hulls import HullClass, HullLayout, ArmorPlate, LAYOUTS, layout_for, MEDIUM_LAYOUT

__all__ = ["Vehicle", "GunVehicle", "Tank", "TankSpec", "TankRenderer", "TANK_PARAMS", "COST_REF",
           "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO", "cost_for",
           "GUN_TUNE_PARAMS", "damage_range", "pen_range", "remap", "TRACKS", "TRACK_SIDES",
           "nominal_damage", "nominal_pen", "GunProfile", "MBT_GUN", "TD_GUN", "default_tuning",
           "TDSpec", "TankDestroyer", "TDRenderer", "TD_PARAMS", "gun_arc_deg",
           "VehicleType", "VEHICLE_TYPES", "RENDERERS", "make_vehicle", "FRONT_SCREEN",
           "AmmoType", "AMMO_TYPES", "AMMO_ORDER", "ammo_stats", "RunningGear",
           "HullClass", "HullLayout", "ArmorPlate", "LAYOUTS", "layout_for", "MEDIUM_LAYOUT"]