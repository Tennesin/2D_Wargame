"""tank — всё, что относится к ОБТ.
Снаружи импортируем через пакет vehicles: from vehicles import Tank, TankSpec, ..."""
from .params import PARAMS, COST_REF, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO
from .spec import TankSpec, cost_for, caliber_range_for, estimate_mass
from .entity import Tank
from .sprites import TankRenderer

__all__ = ["PARAMS", "COST_REF", "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO",
           "TankSpec", "Tank", "TankRenderer", "cost_for", "caliber_range_for", "estimate_mass"]