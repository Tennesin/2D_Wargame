"""editor — части редактора карт: перенос стен в карту и из неё, кнопки, модальные окна.
Снаружи: from game.editor import load_walls, collect_walls, EditorBar, Dialog"""
from .mapio import load_walls, collect_walls
from .toolbar import EditorBar
from .dialogs import Dialog
from .wall_tool import WallTool

__all__ = ["load_walls", "collect_walls", "EditorBar", "Dialog", "WallTool"]