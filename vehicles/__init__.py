"""vehicles — техника. Сейчас только танк; остальные типы появятся рядом (vehicles/btr, ...).
Снаружи: from vehicles import Tank, TankSpec, TankRenderer, TANK_PARAMS"""
from .tank import Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS

__all__ = ["Tank", "TankSpec", "TankRenderer", "TANK_PARAMS"]