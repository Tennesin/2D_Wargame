"""game/content/panels/vehicle.py — панели конструктора техники: по одной на каждый играбельный тип из реестра."""
from functools import partial

from engine import VehicleKind
from vehicles import (
    GUN_TUNE_PARAMS, VEHICLE_TYPES, FRONT_SCREEN, NOSE_FLAT, NOSE_PIKE, NOSE_MIN_FRONT_MM,
    SPECIAL_HEAT, SPECIAL_HESH, HESH_MIN_CAL_MM
)
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow, make_param_row

# Пояснения под ползунком мощности. Это текст интерфейса, поэтому он лежит здесь, а не в реестре техники.
VEHICLE_NOTES = {
    VehicleKind.MBT: (f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм: он усиливает лоб, "
                      "но у очень тяжёлых машин ухудшает разгон и поворот. "
                      "Лобовые экраны защищают от кумулятивных снарядов."),
    VehicleKind.TD: ("Орудие без башни наводится только в узком секторе (УГН), дальше нужно доворачивать корпус. "
                     "Чем крупнее калибр, тем уже сектор и тем дальше назад уезжает орудие. "
                     f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм."),
}

def build_vehicle_panel(kind):
    """Панель конструктора для типа техники kind: ползунки из vt.params плюс блоки характеристик."""
    vt = VEHICLE_TYPES[kind]
    spec0 = vt.spec_cls.from_config()
    row = partial(make_param_row, vt.params)
    tune_row = partial(make_param_row, GUN_TUNE_PARAMS)
    items = [
        SectionHeader("Вооружение"),
        row("gun_caliber_mm"),
        tune_row("gun_damage"),
        tune_row("gun_penetration"),
        tune_row("gun_length_cal"),
        InfoText("Длиннее ствол: быстрее снаряд и дальше полёт, но слабее пробитие, тяжелее орудие, "
                 "медленнее наводка и выше цена. Чем длиннее ствол, тем он тоньше."),
        ChoiceRow("special_ammo", "Спецснаряд (слот 2)",
                  [(SPECIAL_HEAT, "КС"), (SPECIAL_HESH, "HESH")], SPECIAL_HEAT,
                  note=f"калибр от {HESH_MIN_CAL_MM} мм"),

        SectionHeader("Броня"),
        row("front_armor_mm"),
        row("side_armor_mm"),
        row("rear_armor_mm"),
        make_param_row({"front_screen_mm": FRONT_SCREEN}, "front_screen_mm"),
    ]
    if vt.sloped_nose is not None:               # варианты носа обновляет конструктор (хук sloped_nose)
        items.append(ChoiceRow("front_nose", "Нос корпуса",
                               [(NOSE_FLAT, "Плоский"), (NOSE_PIKE, "Щучий")], NOSE_FLAT,
                               note=f"лоб > {NOSE_MIN_FRONT_MM:.0f} мм"))
    items += [
        SectionHeader("Силовая установка"),
        row("engine_power_hp"),
    ]
    note = VEHICLE_NOTES.get(kind)
    if note:
        items.append(InfoText(note))
    items += [
        SectionHeader("Расчётные характеристики"),
        StatsBlock(list(spec0.main_stats())),

        SectionHeader("Внутренние показатели"),
        StatsBlock(list(spec0.internal_stats())),
    ]
    return Panel(f"Конструктор: {vt.label}", items)

def build_vehicle_panels():
    """{VehicleKind: Panel} для всех играбельных типов реестра."""
    return {kind: build_vehicle_panel(kind) for kind, vt in VEHICLE_TYPES.items() if vt.playable}