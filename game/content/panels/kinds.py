"""game/content/panels/kinds.py — режимы панели и соответствие «тип техники → панель»."""
from enum import Enum, auto

from engine import VehicleKind

class PanelMode(Enum):
    TANK = auto()
    WALL = auto()
    TD = auto()

PANEL_OF = {VehicleKind.MBT: PanelMode.TANK, VehicleKind.TD: PanelMode.TD}