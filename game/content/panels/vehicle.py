"""game/content/panels/vehicle.py — панели конструктора техники (ОБТ и ПТ-САУ)."""
from functools import partial

from engine import VehicleKind
from vehicles import (
    TankSpec, TDSpec, TANK_PARAMS, TD_PARAMS, GUN_TUNE_PARAMS, VEHICLE_TYPES,
    FRONT_SCREEN, NOSE_FLAT, NOSE_PIKE, NOSE_MIN_FRONT_MM,
    SPECIAL_HEAT, SPECIAL_HESH, HESH_MIN_CAL_MM
)
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow, make_param_row

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
    note = (f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм: он усиливает лоб, "
            "но у очень тяжёлых машин ухудшает разгон и поворот. "
            "Лобовые экраны защищают от кумулятивных снарядов.")
    return _build_vehicle_panel(_title(VehicleKind.MBT), TANK_PARAMS, TankSpec.from_config(),
                                note=note, with_nose=True)

def build_td_panel():
    note = ("Орудие без башни наводится только в узком секторе (УГН), дальше нужно доворачивать корпус. "
            "Чем крупнее калибр, тем уже сектор и тем дальше назад уезжает орудие. "
            f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм.")
    return _build_vehicle_panel(_title(VehicleKind.TD), TD_PARAMS, TDSpec.from_config(),
                                note=note, with_nose=True)