"""game/content/panels/kinds.py — режимы панели и соответствие «тип техники → панель»."""
from enum import Enum, auto

from engine import VehicleKind

class PanelMode(Enum):
    TANK = auto()
    WALL = auto()
    TD = auto()
    MAP_WALL = auto()
    MAP_ROCK = auto()
    MAP_LAND = auto()

PANEL_OF = {VehicleKind.MBT: PanelMode.TANK, VehicleKind.TD: PanelMode.TD}