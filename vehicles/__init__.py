"""vehicles — техника. Базовое шасси Vehicle, техника с орудием GunVehicle и конкретные типы:
танк (tank) и ПТ-САУ (td). Новые типы добавляются рядом и регистрируются в registry.py.
Снаружи: from vehicles import Vehicle, Tank, TankSpec, TankRenderer, TANK_PARAMS, make_vehicle, ..."""
from vehicles.chassis.vehicle import Vehicle
from vehicles.gun.vehicle import GunVehicle
from vehicles.gun.params import GUN_TUNE_PARAMS, HESH_MIN_CAL_MM
from vehicles.gun.ammo import AmmoType, AMMO_TYPES, AMMO_ORDER, ammo_stats, ammo_kinds, SPECIAL_HEAT, SPECIAL_HESH
from vehicles.chassis.params import FRONT_SCREEN
from vehicles.gun.tuning import (
    damage_range, pen_range, remap, nominal_damage, nominal_pen,
    GunProfile, MBT_GUN, TD_GUN, default_tuning
)
from .tank import (
    Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, COST_REF,
    caliber_range_for, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO, estimate_mass
)
from .cost import cost_for, raw_cost, round_cost
from .gun.vehicle_specific import GunVehicleSpec
from .td import TDSpec, TankDestroyer, TDRenderer, TD_PARAMS, gun_arc_deg
from .spg import SPGSpec, ArtilleryVehicle, SPGRenderer, SPG_PARAMS
from .registry import VehicleType, VEHICLE_TYPES, RENDERERS, make_vehicle
from vehicles.chassis.running_gear import RunningGear, TRACKS, TRACK_SIDES
from vehicles.chassis.hulls import (
    HullClass, HullLayout, ArmorPlate, LAYOUTS, layout_for, MEDIUM_LAYOUT,
    NOSE_FLAT, NOSE_PIKE, NOSE_RU, NOSE_WEDGE
)
from vehicles.chassis.hull_noses import (
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
           "NOSE_FLAT", "NOSE_PIKE", "NOSE_RU", "NOSE_MIN_FRONT_MM", "layout_with_nose", "NOSE_WEDGE",
           "SUPERHEAVY_MASS_T", "WEDGE_ACCEL_K", "WEDGE_TURN_K", "wedge_front_factor",
           "sloped_nose_for_mass", "resolve_nose", "HESH_MIN_CAL_MM", "ammo_kinds",
           "SPECIAL_HEAT", "SPECIAL_HESH", "GunVehicleSpec", "SPGSpec", "ArtilleryVehicle", "SPGRenderer",
           "SPG_PARAMS"]