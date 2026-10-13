"""engine/kinds.py — перечисления: команда техники и тип цели для снарядов."""
from enum import Enum, auto

class Team(Enum):
    PLAYER = auto()
    BOTS = auto()

class VehicleKind(Enum):
    MBT = auto()
    TD = auto()

class TargetType(Enum):
    """Что именно задел снаряд. Нужен уведомлениям и сводке, чтобы не проверять isinstance."""
    VEHICLE = auto()
    WALL = auto()
    TERRAIN = auto()