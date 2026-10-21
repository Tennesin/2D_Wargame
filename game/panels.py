"""game/panels.py — состав панелей интерфейса: какие ползунки и характеристики показывать
для танка и для стены. Единственное место, где интерфейс «знакомится» с танком и стеной."""
from enum import Enum, auto
from functools import partial

from combat import RICOCHET_ANGLE
from engine import VehicleKind
from inputs import Action, key_label
from vehicles import (
    TankSpec, TDSpec, TANK_PARAMS, TD_PARAMS, GUN_TUNE_PARAMS, VEHICLE_TYPES, gun_arc_deg,
    FRONT_SCREEN, nose_front_factor, NOSE_FLAT, NOSE_PIKE, NOSE_MIN_FRONT_MM,
    SUPERHEAVY_MASS_T, WEDGE_ACCEL_K, WEDGE_TURN_K, wedge_front_factor,
    SPECIAL_HEAT, SPECIAL_HESH, HESH_MIN_CAL_MM
)
from structures import WALL_PARAMS, ROTATE_SNAP_DEG
from ui import (Panel, SectionHeader, StatsBlock, InfoText, ActionButton, ChoiceRow,
                make_param_row, DELETE_BUTTON_COLORS)

class PanelMode(Enum):
    TANK = auto()
    WALL = auto()
    TD = auto()

PANEL_OF = {VehicleKind.MBT: PanelMode.TANK, VehicleKind.TD: PanelMode.TD}

# Названия характеристик стены: используются и панелью, и WallEditor.update_stats
STAT_HP = "Текущее HP"
STAT_THICK = "Толщина"
STAT_ARMOR = "Эквивалент брони"
STAT_MASS = "Масса стены"
STAT_ANGLE = "Угол"

def _title(kind):
    return f"Конструктор: {VEHICLE_TYPES[kind].label}"

def _build_vehicle_panel(title, params, spec0, note=None, with_nose=False):
    """Общая панель конструктора: ползунки типа техники + блоки характеристик."""
    row = partial(make_param_row, params)
    tune_row = partial(make_param_row, GUN_TUNE_PARAMS)
    items = [
        SectionHeader("Вооружение"),
        row("gun_caliber_mm"),
        tune_row("gun_damage"),
        tune_row("gun_penetration"),
        ChoiceRow("special_ammo", "Спецснаряд (слот 2)",
                  [(SPECIAL_HEAT, "КС"), (SPECIAL_HESH, "HESH")], SPECIAL_HEAT,
                  note=f"калибр от {HESH_MIN_CAL_MM} мм"),

        SectionHeader("Броня"),
        row("front_armor_mm"),
        row("side_armor_mm"),
        row("rear_armor_mm"),
        make_param_row({"front_screen_mm": FRONT_SCREEN}, "front_screen_mm"),
    ]
    if with_nose:
        items.append(ChoiceRow("front_nose", "Нос корпуса",
                               [(NOSE_FLAT, "Плоский"), (NOSE_PIKE, "Щучий")], NOSE_FLAT,
                               note=f"лоб > {NOSE_MIN_FRONT_MM:.0f} мм"))
    items += [
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
    gain = nose_front_factor() * 100.0
    wedge = wedge_front_factor() * 100.0
    note = (f"Скошенный нос зависит от массы. До {SUPERHEAVY_MASS_T:.0f} т это щучий нос: двускатный лоб, "
            f"при ударе строго по оси приведённая броня составляет около {gain:.0f}% от значения «Лоб». "
            f"От {SUPERHEAVY_MASS_T:.0f} т ставится клин: плоская плита по центру (ровно «Лоб») и два скоса "
            f"по бокам (около {wedge:.0f}%). Клин тяжелее: начальный разгон хуже на "
            f"{(1.0 - WEDGE_ACCEL_K) * 100:.0f}%, поворот корпуса на {(1.0 - WEDGE_TURN_K) * 100:.0f}%. "
            f"Доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм. "
            "Лобовые экраны: четыре тонких листа; КС срабатывает на них только при прямом попадании.")
    return _build_vehicle_panel(_title(VehicleKind.MBT), TANK_PARAMS, TankSpec.from_config(),
                                note=note, with_nose=True)

def build_td_panel():
    cal = TD_PARAMS["gun_caliber_mm"]
    wide = gun_arc_deg(cal.min) / 2.0        # УГН у самого малого калибра
    narrow = gun_arc_deg(cal.max) / 2.0      # и у самого крупного
    note = (f"Орудие без башни: наводка только в пределах УГН (от ±{wide:.0f}° у малых калибров "
            f"до ±{narrow:.0f}° у крупных), дальше нужно доворачивать корпус. "
            "Чем крупнее калибр, тем дальше назад уезжает орудие и появляется задняя опора. "
            "Урон и пробитие выше, чем у ОБТ того же калибра, при той же перезарядке. "
            "Щучий нос (двускатный лоб) доступен при лобовой броне больше "
            f"{NOSE_MIN_FRONT_MM:.0f} мм. "
            )
    return _build_vehicle_panel(_title(VehicleKind.TD), TD_PARAMS, TDSpec.from_config(),
                                note=note, with_nose=True)

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