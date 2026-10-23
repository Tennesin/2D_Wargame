"""game/content/panels/wall.py — панель настроек стены."""
from functools import partial

from combat import RICOCHET_ANGLE
from engine import fmt_num
from inputs import Action, key_label
from structures import WALL_PARAMS, ROTATE_SNAP_DEG
from ui import (Panel, SectionHeader, StatsBlock, InfoText, ActionButton,
                make_param_row, DELETE_BUTTON_COLORS)
from .kinds import PanelMode

# Названия характеристик стены: используются и панелью, и WallEditor.update_stats
STAT_HP = "Текущее HP"
STAT_THICK = "Толщина"
STAT_ARMOR = "Эквивалент брони"
STAT_MASS = "Масса стены"
STAT_ANGLE = "Угол"

def build_wall_panel():
    """Колбэк красной кнопки здесь не задаётся: его привязывает WallEditor (bind_wall_delete)."""
    row = partial(make_param_row, WALL_PARAMS)
    return Panel("Настройки стены", [
        SectionHeader("Параметры"),
        row("wall_hp"),
        row("wall_width_m"),
        row("wall_length_m"),

        SectionHeader("Расчётные характеристики"),
        StatsBlock([STAT_HP, STAT_THICK, STAT_ARMOR, STAT_MASS, STAT_ANGLE]),
        InfoText("Толщина — меньшая из сторон. Эквивалент брони растёт при косом попадании "
                 f"(броня / cos угла), а при угле больше {RICOCHET_ANGLE:.0f}° снаряд рикошетит. "
                 f"Белая точка в центре поворачивает стену; с Shift поворот идёт шагом {ROTATE_SNAP_DEG:.0f}°. "
                 f"{key_label(Action.DELETE_WALL)} — удалить выбранную стену."),

        ActionButton("Удалить стену", DELETE_BUTTON_COLORS),
    ])

def wall_values(wall):
    """Значения ползунков панели стены для конкретной стены."""
    return {"wall_hp": wall.max_hp, "wall_width_m": wall.width_m, "wall_length_m": wall.length_m}

def bind_wall_delete(ui, callback):
    """Привязать действие к красной кнопке «Удалить стену» панели стены."""
    for item in ui.panels[PanelMode.WALL].items:
        if isinstance(item, ActionButton):
            item.callback = callback

class WallPanelLink:
    """Связка панели настроек стены с WallEditor: ползунки меняют стену,
    а числа стены попадают на панель. Редактор про панель ничего не знает."""

    def __init__(self, ui, editor, walls):
        self.ui = ui
        self.editor = editor
        self.walls = walls
        self._stats_key = None           # последние показанные значения стены

        ui.set_on_change(PanelMode.WALL, self._on_params_change)
        bind_wall_delete(ui, editor.delete_selected)

    def _on_params_change(self, values):
        """Ползунок сдвинут. Если стена не поместилась, возвращаем на панель прежние значения."""
        wall = self.walls.selected
        if wall is None:
            return
        ok = self.editor.apply_params(wall, values["wall_hp"], values["wall_width_m"],
                                      values["wall_length_m"])
        if not ok:
            self.ui.set_values(PanelMode.WALL, wall_values(wall))

    def update_stats(self):
        """Пишем в панель только если выбрана стена и значения изменились.
        Выбранная стена бывает только в режиме WALL_EDIT, отдельная проверка режима не нужна."""
        wall = self.walls.selected
        if wall is None:
            return
        key = (wall.hp, wall.max_hp, wall.width_m, wall.length_m, wall.angle)
        if key == self._stats_key:
            return
        self._stats_key = key
        self.ui.set_stat(PanelMode.WALL, STAT_HP, f"{fmt_num(wall.hp)} / {fmt_num(wall.max_hp)}")
        self.ui.set_stat(PanelMode.WALL, STAT_MASS, f"{fmt_num(wall.mass_t, 1)} т")
        self.ui.set_stat(PanelMode.WALL, STAT_THICK, f"{wall.thickness_m:.2f} м")
        self.ui.set_stat(PanelMode.WALL, STAT_ARMOR, f"{wall.armor_mm:.0f} мм")
        self.ui.set_stat(PanelMode.WALL, STAT_ANGLE, f"{wall.angle:.0f} °")