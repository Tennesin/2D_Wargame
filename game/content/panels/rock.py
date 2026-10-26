"""game/content/panels/rock.py — элементы панели настроек камня (редактор карт) и связка с RockTool."""
from functools import partial

from ui import SectionHeader, StatsBlock, ActionButton, make_param_row, DELETE_BUTTON_COLORS
from world import ROCK_PARAMS
from .kinds import PanelMode
from .wall import bind_wall_delete          # найдёт первую ActionButton панели: подходит и камню

STAT_NAMES = ("Средняя толщина", "Наименьшая толщина", "Масса")      # как в Patch.describe()

def rock_items():
    row = partial(make_param_row, ROCK_PARAMS)
    return [
        SectionHeader("Параметры камня"),
        row("rock_radius_m"),
        row("rock_stability"),
        row("rock_smooth"),
        SectionHeader("Выбранный камень"),
        StatsBlock(list(STAT_NAMES)),
        ActionButton("Удалить камень", DELETE_BUTTON_COLORS),
    ]

class RockPanelLink:
    """Ползунки панели дают форму новых камней, а числа выбранного камня попадают на панель."""

    def __init__(self, ui, tool, mode=PanelMode.MAP_ROCK):
        self.ui = ui
        self.tool = tool
        self.mode = mode
        self._delete = bind_wall_delete(ui, mode, tool.delete_selected)
        tool.on_select = self.on_select
        tool.get_params = self.template
        self.on_select(None)

    def template(self):
        return self.ui.get_values(self.mode)

    def on_select(self, patch):
        if self._delete is not None:
            self._delete.button.enabled = patch is not None
        if patch is None:
            for name in STAT_NAMES:
                self.ui.set_stat(self.mode, name, "—")
            return
        _, rows = patch.describe()
        for name, value in rows:
            self.ui.set_stat(self.mode, name, value)