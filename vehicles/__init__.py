"""vehicles — техника. Базовое шасси Vehicle, техника с орудием GunVehicle и конкретные типы:
танк (tank) и ПТ-САУ (td). Новые типы добавляются рядом и регистрируются в registry.py.
Снаружи: from vehicles import Vehicle, Tank, TankSpec, TankRenderer, TANK_PARAMS, make_vehicle, ..."""
from .base import Vehicle
from .gun_vehicle import GunVehicle
from .gun_params import GUN_TUNE_PARAMS, HESH_MIN_CAL_MM
from .ammo import AmmoType, AMMO_TYPES, AMMO_ORDER, ammo_stats, ammo_kinds, SPECIAL_HEAT, SPECIAL_HESH
from .chassis_params import FRONT_SCREEN
from .gun_tuning import (
    damage_range, pen_range, remap, nominal_damage, nominal_pen,
    GunProfile, MBT_GUN, TD_GUN, default_tuning
)
from .tank import (
    Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF, cost_for, raw_cost,
    caliber_range_for, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO, estimate_mass
)
from .td import TDSpec, TankDestroyer, TDRenderer, TD_PARAMS, gun_arc_deg
from .registry import VehicleType, VEHICLE_TYPES, RENDERERS, make_vehicle
from .running_gear import RunningGear, TRACKS, TRACK_SIDES
from .hulls import (
    HullClass, HullLayout, ArmorPlate, LAYOUTS, layout_for, MEDIUM_LAYOUT,
    NOSE_FLAT, NOSE_PIKE, NOSE_RU, NOSE_WEDGE
)
from .hull_noses import (
    NOSE_MIN_FRONT_MM, layout_with_nose, nose_front_factor, SUPERHEAVY_MASS_T,
    WEDGE_ACCEL_K, WEDGE_TURN_K, wedge_front_factor, sloped_nose_for_mass, resolve_nose
)

__all__ = ["Vehicle", "GunVehicle", "Tank", "TankSpec", "TankRenderer", "TANK_PARAMS", "COST_REF",
           "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO", "cost_for", "caliber_range_for",
           "GUN_TUNE_PARAMS", "damage_range", "pen_range", "remap", "TRACKS", "TRACK_SIDES",
           "nominal_damage", "nominal_pen", "GunProfile", "MBT_GUN", "TD_GUN", "default_tuning",
           "TDSpec", "TankDestroyer", "TDRenderer", "TD_PARAMS", "gun_arc_deg", "estimate_mass",
           "VehicleType", "VEHICLE_TYPES", "RENDERERS", "make_vehicle", "FRONT_SCREEN", "raw_cost",
           "AmmoType", "AMMO_TYPES", "AMMO_ORDER", "ammo_stats", "RunningGear", "nose_front_factor",
           "HullClass", "HullLayout", "ArmorPlate", "LAYOUTS", "layout_for", "MEDIUM_LAYOUT",
           "NOSE_FLAT", "NOSE_PIKE", "NOSE_RU", "NOSE_MIN_FRONT_MM", "layout_with_nose",
           "NOSE_WEDGE", "SUPERHEAVY_MASS_T", "WEDGE_ACCEL_K", "WEDGE_TURN_K", "wedge_front_factor",
           "sloped_nose_for_mass", "resolve_nose", "HESH_MIN_CAL_MM", "ammo_kinds",
           "SPECIAL_HEAT", "SPECIAL_HESH"]