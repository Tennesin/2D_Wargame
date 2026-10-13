"""td — ПТ-САУ. Снаружи импортируем через пакет vehicles."""
from .params import TD_PARAMS
from .spec import TDSpec
from .entity import TankDestroyer
from .sprites import TDRenderer

__all__ = ["TD_PARAMS", "TDSpec", "TankDestroyer", "TDRenderer"]