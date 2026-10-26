"""editor — части редактора карт: перенос стен в карту и из неё, кнопки, модальные окна, инструменты.
Снаружи: from game.editor import WallTool, RockTool, LandTool, EditorBar, Dialog, ..."""
from .mapio import load_walls, collect_walls
from .toolbar import EditorBar
from .dialogs import Dialog
from .wall_tool import WallTool
from .rock_tool import RockTool
from .land_tool import LandTool
from .overlays import RockOverlay, BrushOverlay

__all__ = ["load_walls", "collect_walls", "EditorBar", "Dialog", "WallTool",
           "RockTool", "LandTool", "RockOverlay", "BrushOverlay"]