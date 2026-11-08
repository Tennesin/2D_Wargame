"""game/content/panels/vehicle.py — панели конструктора техники: «Сборка» для каждого играбельного типа
и «Дизайн» для типов, у которых есть дизайн (сейчас ОБТ). Ключ панели: (VehicleKind, "build" | "design")."""
from functools import partial

from engine import VehicleKind
from vehicles import (
    GUN_TUNE_PARAMS, VEHICLE_TYPES, FRONT_SCREEN, NOSE_FLAT, NOSE_PIKE, NOSE_MIN_FRONT_MM,
    SPECIAL_HEAT, SPECIAL_HESH, HESH_MIN_CAL_MM,
    TURRET_STYLES, TURRET_STYLE_RU, DESIGN_PARAMS
)
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow, make_param_row

# Пояснения под ползунком мощности. Это текст интерфейса, поэтому он лежит здесь, а не в реестре техники.
VEHICLE_NOTES = {
    VehicleKind.MBT: (f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм: он усиливает лоб, "
                      "но у очень тяжёлых машин ухудшает разгон и поворот. "
                      "Лобовые экраны защищают от кумулятивных снарядов."),
    VehicleKind.TD: ("Орудие без башни наводится только в узком секторе (УГН), дальше нужно доворачивать корпус. "
                     "Чем крупнее калибр, тем уже сектор и тем дальше назад уезжает орудие. "
                     "Допустимый калибр зависит от брони: на тяжёлой машине мелкое орудие недоступно, "
                     "на очень тонкой недоступны самые крупные калибры. "
                     "Чем толще броня, тем крупнее корпус. "
                     f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм."),
}

# Какие расчётные строки показывать на вкладке «Дизайн»
DESIGN_STATS = {
    VehicleKind.MBT: ("Стоимость", "Масса", "Масса башни", "Инерция башни", "Поворот башни", "Перезарядка"),
    VehicleKind.TD: ("Стоимость", "Масса", "Масштаб корпуса", "Крепление орудия", "Ось орудия от центра",
                     "Поворот корпуса", "Перезарядка"),
}

def _tab_row(tab):
    """Переключатель вкладок; его значение читает ConstructorScene._on_change."""
    return ChoiceRow("tab", "Раздел", [("build", "Сборка"), ("design", "Дизайн")], tab)

def build_vehicle_panel(kind):
    """Вкладка «Сборка» для типа техники kind: ползунки из vt.params плюс блоки характеристик."""
    vt = VEHICLE_TYPES[kind]
    spec0 = vt.spec_cls.from_config()
    row = partial(make_param_row, vt.params)
    tune_row = partial(make_param_row, GUN_TUNE_PARAMS)
    items = []
    if vt.design_defaults:
        items.append(_tab_row("build"))
    items += [
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

def build_design_panel(kind):
    """Вкладка «Дизайн»: параметры типа техники и то, на что они влияют."""
    vt = VEHICLE_TYPES[kind]
    items = [_tab_row("design")]
    if kind is VehicleKind.MBT:
        items += [
            InfoText("Кольцо в превью: ось башни. Крестик: центр корпуса. Сдвиг оси двигает башню вдоль корпуса, "
                     "вместе с ней смещаются дульный срез и точка вращения."),
            SectionHeader("Башня"),
            ChoiceRow("turret_style", "Форма башни",
                      [(s, TURRET_STYLE_RU[s]) for s in TURRET_STYLES], "auto"),
            make_param_row(DESIGN_PARAMS, "turret_size"),
            make_param_row(DESIGN_PARAMS, "turret_axis_shift_m"),
            InfoText("«Авто»: форма по классу корпуса (лёгкий: овал, средний: гекс, тяжёлый: плита). "
                     "Больше башня: тяжелее, медленнее наводка и дороже, зато быстрее заряжание. "
                     "Меньше: легче и быстрее наводится, но экипажу тесно и перезарядка дольше."),
        ]
    else:
        items += [
            InfoText("Кольцо в превью: ось орудия. Крестик: центр корпуса. Корпус поворачивается вокруг оси орудия: "
                     "у носового орудия при развороте уходит в сторону корма, у кормового нос."),
            SectionHeader("Орудие"),
            make_param_row(DESIGN_PARAMS, "mount_shift_m"),
            InfoText("Сдвиг считается от положения по умолчанию, которое зависит от калибра. "
                     "Мелкое орудие нельзя увести далеко к корме, крупное нельзя вынести далеко в нос."),
        ]
    items += [
        SectionHeader("Влияние на характеристики"),
        StatsBlock(list(DESIGN_STATS[kind])),
    ]
    return Panel(f"Конструктор: {vt.label}: дизайн", items)

def build_vehicle_panels():
    """{(VehicleKind, вкладка): Panel} для всех играбельных типов реестра."""
    panels = {}
    for kind, vt in VEHICLE_TYPES.items():
        if not vt.playable:
            continue
        panels[(kind, "build")] = build_vehicle_panel(kind)
        if vt.design_defaults:
            panels[(kind, "design")] = build_design_panel(kind)
    return panels