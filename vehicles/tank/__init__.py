"""tank — всё, что относится к ОБТ.
Снаружи импортируем через пакет vehicles: from vehicles import Tank, TankSpec, ..."""
# ВАЖНО: порядок импортов ниже менять нельзя. vehicles/cost.py импортирует tank.params,
# а tank.spec (через gun/vehicle_specific.py) импортирует cost. Цикла нет, только пока
# params подгружается первым.
from .params import PARAMS, COST_REF, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO
from .spec import TankSpec, caliber_range_for, estimate_mass
from .entity import Tank
from .sprites import TankRenderer

__all__ = [
    "PARAMS", "COST_REF", "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO",
    "TankSpec", "Tank", "TankRenderer", "caliber_range_for", "estimate_mass"
]