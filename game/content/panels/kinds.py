"""game/content/panels/kinds.py — режимы панели редактора карт. У конструктора режим панели = VehicleKind."""
from enum import Enum, auto

class PanelMode(Enum):
    MAP_WALL = auto()
    MAP_ROCK = auto()
    MAP_LAND = auto()