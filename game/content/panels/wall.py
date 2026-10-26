"""game/content/panels/wall.py — элементы панели настроек стены (в редакторе карт) и связка с WallTool."""
from functools import partial

from engine import fmt_num
from structures import WALL_PARAMS
from ui import SectionHeader, StatsBlock, ActionButton, make_param_row, DELETE_BUTTON_COLORS
from .kinds import PanelMode

STAT_HP = "Текущее HP"
STAT_THICK = "Толщина"
STAT_ARMOR = "Эквивалент брони"
STAT_MASS = "Масса стены"
STAT_ANGLE = "Угол"
STAT_NAMES = (STAT_HP, STAT_THICK, STAT_ARMOR, STAT_MASS, STAT_ANGLE)

def wall_items():
    """Элементы панели: ползунки (шаблон новой стены или правка выбранной), сведения и кнопка удаления."""
    row = partial(make_param_row, WALL_PARAMS)
    return [
        SectionHeader("Параметры стены"),
        row("wall_hp"),
        row("wall_width_m"),
        row("wall_length_m"),

        SectionHeader("Выбранная стена"),
        StatsBlock(list(STAT_NAMES)),
        ActionButton("Удалить стену", DELETE_BUTTON_COLORS),
    ]

def wall_values(wall):
    """Значения ползунков панели для конкретной стены."""
    return {"wall_hp": wall.max_hp, "wall_width_m": wall.width_m, "wall_length_m": wall.length_m}

def bind_wall_delete(ui, mode, callback):
    """Привязать действие к красной кнопке панели mode. Возвращает саму кнопку (ActionButton)."""
    for item in ui.panels[mode].items:
        if isinstance(item, ActionButton):
            item.callback = callback
            return item
    return None

class WallPanelLink:
    """Связка панели настроек стены с WallTool: ползунки меняют выбранную стену (или остаются шаблоном
    для новых), а числа выбранной стены попадают на панель. Сам инструмент про панель ничего не знает."""

    def __init__(self, ui, tool, mode=PanelMode.MAP_WALL):
        self.ui = ui
        self.tool = tool
        self.mode = mode
        self._stats_key = None
        self._delete = bind_wall_delete(ui, mode, tool.delete_selected)
        tool.on_select = self.on_select
        tool.get_params = self.template
        self.on_select(None)

    def template(self):
        """Значения ползунков: параметры для новой стены."""
        return self.ui.get_values(self.mode)

    def on_params_change(self, values):
        """Ползунок сдвинут. Выбрана стена: правим её; не поместилась: возвращаем прежние значения на панель."""
        wall = self.tool.walls.selected
        if wall is None:
            return
        if not self.tool.apply_params(values):
            self.ui.set_values(self.mode, wall_values(wall))

    def on_select(self, wall):
        """Выбор изменился: кнопка удаления, значения ползунков и сведения."""
        self._stats_key = None
        if self._delete is not None:
            self._delete.button.enabled = wall is not None
        if wall is None:
            for name in STAT_NAMES:
                self.ui.set_stat(self.mode, name, "—")
        else:
            self.ui.set_values(self.mode, wall_values(wall))
            self.update_stats()

    def update_stats(self):
        """Пишем в панель только если выбрана стена и её значения изменились."""
        wall = self.tool.walls.selected
        if wall is None:
            return
        key = (wall.hp, wall.max_hp, wall.width_m, wall.length_m, wall.angle)
        if key == self._stats_key:
            return
        self._stats_key = key
        s = self.ui.set_stat
        s(self.mode, STAT_HP, f"{fmt_num(wall.hp)} / {fmt_num(wall.max_hp)}")
        s(self.mode, STAT_MASS, f"{fmt_num(wall.mass_t, 1)} т")
        s(self.mode, STAT_THICK, f"{wall.thickness_m:.2f} м")
        s(self.mode, STAT_ARMOR, f"{wall.armor_mm:.0f} мм")
        s(self.mode, STAT_ANGLE, f"{wall.angle:.0f} °")