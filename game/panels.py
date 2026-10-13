"""game/panels.py — состав панелей интерфейса: какие ползунки и характеристики показывать
для танка и для стены. Единственное место, где интерфейс «знакомится» с танком и стеной."""
from enum import Enum, auto
from functools import partial

from engine import VehicleKind
from vehicles import TankSpec, TDSpec, TANK_PARAMS, TD_PARAMS, GUN_TUNE_PARAMS
from structures import WALL_PARAMS
from ui import (Panel, SectionHeader, StatsBlock, InfoText, ActionButton,
                make_param_row, DELETE_BUTTON_COLORS)

class PanelMode(Enum):
    TANK = auto()
    WALL = auto()
    TD = auto()

PANEL_OF = {VehicleKind.MBT: PanelMode.TANK, VehicleKind.TD: PanelMode.TD}

def _build_vehicle_panel(title, params, spec0, note=None):
    """Общая панель конструктора: ползунки типа техники + блоки характеристик."""
    row = partial(make_param_row, params)
    tune_row = partial(make_param_row, GUN_TUNE_PARAMS)
    items = [
        SectionHeader("Вооружение"),
        row("gun_caliber_mm"),
        tune_row("gun_damage"),
        tune_row("gun_penetration"),

        SectionHeader("Броня"),
        row("front_armor_mm"),
        row("side_armor_mm"),
        row("rear_armor_mm"),

        SectionHeader("Силовая установка"),
        row("engine_power_hp"),
    ]
    if note:
        items.append(InfoText(note))
    items += [
        SectionHeader("Расчётные характеристики"),
        StatsBlock(list(spec0.main_stats())),

        SectionHeader("Внутренние показатели"),
        StatsBlock(list(spec0.internal_stats())),
    ]
    return Panel(title, items)

def build_tank_panel():
    return _build_vehicle_panel("Конструктор: ОБТ", TANK_PARAMS, TankSpec.from_config())

def build_td_panel():
    return _build_vehicle_panel(
        "Конструктор: ПТ-САУ", TD_PARAMS, TDSpec.from_config(),
        note="Орудие без башни: наводка только в пределах УГН (±15° от оси корпуса), "
             "дальше нужно доворачивать корпус. Чем крупнее калибр, тем дальше назад "
             "уезжает орудие и появляется задняя опора. Урон и пробитие выше, чем у ОБТ "
             "того же калибра, при той же перезарядке.")

def build_wall_panel():
    """Колбэк красной кнопки здесь не задаётся: его привязывает WallEditor (bind_wall_delete)."""
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