"""content/panels — состав панелей интерфейса: какие ползунки и характеристики показывать
для танка и для стены. Единственное место, где интерфейс «знакомится» с танком и стеной.
Снаружи импортируем из пакета: from ..content.panels import PanelMode, build_tank_panel, ..."""
from .kinds import PanelMode, PANEL_OF
from .vehicle import build_tank_panel, build_td_panel
from .wall import (build_wall_panel, wall_values, bind_wall_delete,
                   STAT_HP, STAT_THICK, STAT_ARMOR, STAT_MASS, STAT_ANGLE)

__all__ = ["PanelMode", "PANEL_OF", "build_tank_panel", "build_td_panel",
           "build_wall_panel", "wall_values", "bind_wall_delete",
           "STAT_HP", "STAT_THICK", "STAT_ARMOR", "STAT_MASS", "STAT_ANGLE"]