"""tank — всё, что относится к танку.
Снаружи импортируем через пакет vehicles: from vehicles import Tank, TankSpec, ...
Внутренности (spec.py, sprites.py, ...) снаружи не трогаем."""
from .params import (PARAMS, COST_REF, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO,
                     GUN_TUNE_PARAMS)
from .spec import TankSpec, cost_for
from .entity import Tank
from .sprites import TankRenderer
from .gun_tuning import damage_range, pen_range, remap

__all__ = ["PARAMS", "COST_REF", "LOOK_FRONT_RATIO", "LOOK_GUN_RATIO", "LOOK_SPEED_RATIO",
           "TankSpec", "Tank", "TankRenderer", "cost_for",
           "GUN_TUNE_PARAMS", "damage_range", "pen_range", "remap"]