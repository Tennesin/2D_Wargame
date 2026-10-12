"""ui — виджеты, панели, тулбар и HUD. О танке и стене не знает: состав панелей приходит снаружи.
Снаружи: from ui import ConstructorUI, Panel, ToolBar, TankHud, ..."""
from .theme import DELETE_BUTTON_COLORS, ACTIVE_BUTTON_COLORS
from .widgets import (Button, Slider, ScrollArea, SectionHeader, ParamRow, make_param_row,
                      StatsBlock, InfoText, ActionButton)
from .toolbar import ToolBar
from .panel import Panel, SidePanel
from .hud import TankHud
from .info_card import InfoCard

__all__ = ["DELETE_BUTTON_COLORS", "ACTIVE_BUTTON_COLORS", "Button", "Slider", "ScrollArea",
           "SectionHeader", "ParamRow", "make_param_row", "StatsBlock", "InfoText",
           "ActionButton", "ToolBar", "Panel", "SidePanel", "TankHud", "InfoCard"]