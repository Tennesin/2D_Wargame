"""content/panels/wall.py — панель настроек стены."""
from functools import partial

from combat import RICOCHET_ANGLE
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