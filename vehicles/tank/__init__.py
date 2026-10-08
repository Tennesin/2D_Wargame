"""tank — всё, что относится к танку.
Снаружи импортируем через пакет vehicles: from vehicles import Tank, TankSpec, ...
Внутренности (spec.py, sprites.py, ...) снаружи не трогаем."""
from .params import PARAMS
from .spec import TankSpec
from .entity import Tank
from .sprites import TankRenderer

__all__ = ["PARAMS", "TankSpec", "Tank", "TankRenderer"]