"""content/panels — состав панелей интерфейса: какие ползунки и характеристики показывать
для танка, стены и редактора карт. Единственное место, где интерфейс «знакомится» с танком и стеной.
Снаружи импортируем из пакета: from ..content.panels import PanelMode, build_tank_panel, ..."""
from .kinds import PanelMode, PANEL_OF
from .vehicle import build_tank_panel, build_td_panel
from .wall import wall_items, wall_values, bind_wall_delete, WallPanelLink
from .editor import (build_editor_panels, EDITOR_TOOLS, TOOL_MODE,
                     STAT_NAME, STAT_SIZE, STAT_ROCKS, STAT_WALLS, STAT_FILE)
from .rock import rock_items, RockPanelLink
from .land import land_items, LandPanelLink

__all__ = ["PanelMode", "PANEL_OF", "build_tank_panel", "build_td_panel",
           "wall_values", "bind_wall_delete", "WallPanelLink", "wall_items",
           "build_editor_panels", "EDITOR_TOOLS", "TOOL_MODE",
           "STAT_NAME", "STAT_SIZE", "STAT_ROCKS", "STAT_WALLS", "STAT_FILE",
           "rock_items", "RockPanelLink", "land_items", "LandPanelLink"]