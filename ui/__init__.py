"""ui — виджеты, панели, тулбар и HUD. О танке и стене не знает: состав панелей приходит снаружи.
Снаружи: from ui import SidePanel, Panel, ToolBar, TankHud, ..."""
from .theme import DELETE_BUTTON_COLORS, ACTIVE_BUTTON_COLORS
from .widgets import (Button, Checkbox, Slider, ScrollArea, SectionHeader, ParamRow, make_param_row,
                      StatsBlock, InfoText, ActionButton)
from .toolbar import ToolBar
from .panel import Panel, SidePanel
from .hud import TankHud
from .info_card import InfoCard
from .ammo_bar import AmmoBar

__all__ = ["DELETE_BUTTON_COLORS", "ACTIVE_BUTTON_COLORS", "Button", "Checkbox", "Slider", "ScrollArea",
           "SectionHeader", "ParamRow", "make_param_row", "StatsBlock", "InfoText", "AmmoBar",
           "ActionButton", "ToolBar", "Panel", "SidePanel", "TankHud", "InfoCard"]