"""ui_panels.py — состав панелей интерфейса: какие ползунки и характеристики показывать
для танка и для стены. Единственное место, где интерфейс «знакомится» с танком и стеной
(сам ui.py о них ничего не знает)."""
from enum import Enum, auto
from functools import partial

from tank import TankSpec, PARAMS
from wall import WALL_PARAMS
from ui import (Panel, SectionHeader, StatsBlock, InfoText, ActionButton,
                make_param_row, DELETE_BUTTON_COLORS)

class PanelMode(Enum):
    TANK = auto()
    WALL = auto()

def build_tank_panel():
    spec0 = TankSpec.from_config()      # нужен только ради списка названий характеристик
    row = partial(make_param_row, PARAMS)
    return Panel("Конструктор техники", [
        SectionHeader("Вооружение"),
        row("gun_caliber_mm"),

        SectionHeader("Броня"),
        row("front_armor_mm"),
        row("side_armor_mm"),
        row("rear_armor_mm"),

        SectionHeader("Силовая установка"),
        row("engine_power_hp"),

        SectionHeader("Расчётные характеристики"),
        StatsBlock(list(spec0.main_stats())),

        SectionHeader("Внутренние показатели"),
        StatsBlock(list(spec0.internal_stats())),
    ])

def build_wall_panel(on_delete):
    row = partial(make_param_row, WALL_PARAMS)
    return Panel("Настройки стены", [
        SectionHeader("Параметры"),
        row("wall_hp"),
        row("wall_width_m"),
        row("wall_length_m"),

        SectionHeader("Расчётные характеристики"),
        StatsBlock(["Текущее HP", "Толщина", "Эквивалент брони", "Масса стены", "Угол"]),
        InfoText("Толщина — меньшая из сторон. Эквивалент брони растёт при косом попадании "
                 "(броня / cos угла), а при угле больше 70° снаряд рикошетит. "
                 "Белая точка в центре поворачивает стену; с Shift поворот идёт шагом 15°. "
                 "Delete — удалить выбранную стену."),

        ActionButton("Удалить стену", DELETE_BUTTON_COLORS, on_delete),
    ])

def build_panels(on_wall_delete):
    """Все панели: {PanelMode: Panel}."""
    return {
        PanelMode.TANK: build_tank_panel(),
        PanelMode.WALL: build_wall_panel(on_wall_delete),
    }