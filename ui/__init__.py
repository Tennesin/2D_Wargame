"""ui — виджеты, панели, тулбар и HUD. Состав панелей приходит снаружи (game/content/panels);
исключения: TankHud читает данные танка, а ToolBar привязан к кнопке стены.
Снаружи: from ui import SidePanel, Panel, ToolBar, TankHud, ..."""
from .theme import DELETE_BUTTON_COLORS, ACTIVE_BUTTON_COLORS
from .widgets import (Button, Checkbox, Slider, ScrollArea, SectionHeader, ParamRow, make_param_row,
                      StatsBlock, InfoText, ActionButton, ChoiceRow)
from .toolbar import ToolBar
from .panel import Panel, SidePanel
from .hud import TankHud
from .info_card import InfoCard
from .ammo_bar import AmmoBar
from .guide_blocks import IconRow, KeyRow, make_mouse_icon, make_swatch_icon
from .plate import draw_plate

__all__ = ["DELETE_BUTTON_COLORS", "ACTIVE_BUTTON_COLORS", "Button", "Checkbox", "Slider", "ScrollArea",
           "SectionHeader", "ParamRow", "make_param_row", "StatsBlock", "InfoText", "AmmoBar",
           "ActionButton", "ToolBar", "Panel", "SidePanel", "TankHud", "InfoCard", "ChoiceRow",
           "IconRow", "KeyRow", "make_mouse_icon", "make_swatch_icon", "draw_plate"]