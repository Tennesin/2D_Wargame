"""game/content/guide/page_vehicles.py — страница инструкции «Техника»."""
import pygame

from engine import PX_PER_M, VehicleKind
from ui import SectionHeader, InfoText, AccordionRow
from vehicles import (VEHICLE_TYPES, RENDERERS, make_vehicle, TD_GUN, FRONT_SCREEN, NOSE_MIN_FRONT_MM,
                      SUPERHEAVY_MASS_T, WEDGE_ACCEL_K, WEDGE_TURN_K, HESH_MIN_CAL_MM)
from vehicles.chassis.params import SCREEN_TURN_LOSS
from vehicles.gun.params import CALIBER, GUN_DAMAGE_RANGE, GUN_PEN_RANGE, HEAT_SCREEN_PEN_K
from vehicles.tank.hull_rules import CAL_MAX_AT_LIGHT, CAL_MIN_AT_HEAVY
from vehicles.td.params import (TD_ARC_MAX_DEG, TD_ARC_MIN_DEG, MOUNT_CAL,
                                TD_TRAVERSE_MIN, TD_TRAVERSE_MAX)
from .. import texts

VEHICLE_ICON_SIZE = (170, 190)
VEHICLE_ICON_ZOOM_LEVEL = 5          # ступень зума камеры, при которой техника со стволом влезает в иконку
VEHICLE_ICON_CENTER_Y = -180.0       # камера чуть выше центра танка: ствол смотрит вверх
VEHICLE_ICON_BG = (36, 40, 46)

def vehicle_icon(kind):
    """Картинка техники: рисуем её тем же рендерером, что и в игре, на плашку нужного размера."""
    vtype = VEHICLE_TYPES[kind]
    vehicle = make_vehicle(kind, vtype.spec_cls.from_config())
    camera = Camera(*VEHICLE_ICON_SIZE)
    camera.zoom_by(VEHICLE_ICON_ZOOM_LEVEL - camera.zoom_level)
    camera.center_on(0.0, VEHICLE_ICON_CENTER_Y)
    renderer = RENDERERS[vtype.renderer_key]()
    renderer.set_zoom(PX_PER_M * camera.zoom)

    surf = pygame.Surface(VEHICLE_ICON_SIZE)
    surf.fill(VEHICLE_ICON_BG)
    renderer.draw(surf, camera, vehicle)
    return surf

def _bonus(pair):
    return f"от {(pair[0] - 1) * 100:+.0f}% до {(pair[1] - 1) * 100:+.0f}%"

def _mbt_details():
    return [
        "Башня вращается на 360°: можно ехать в одну сторону и стрелять в другую.",
        "Класс корпуса (лёгкий, средний, тяжёлый) задаётся бронёй и мощностью двигателя: много брони "
        "и мало мощности делают корпус тяжелее. От класса зависит силуэт машины и положение оси башни.",
        f"Класс ограничивает калибр: у самого лёгкого корпуса он от {CALIBER.min:.0f} до {CAL_MAX_AT_LIGHT:.0f} мм, "
        f"у самого тяжёлого от {CAL_MIN_AT_HEAVY:.0f} до {CALIBER.max:.0f} мм, у средних границы плавно "
        "сдвигаются между этими значениями. Ползунок калибра подстраивается сам.",
        f"Скошенный нос доступен при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм. Машины тяжелее "
        f"{SUPERHEAVY_MASS_T:.0f} т получают клин вместо щучьего носа: он ухудшает разгон (×{WEDGE_ACCEL_K:g}) "
        f"и поворот корпуса (×{WEDGE_TURN_K:g}).",
        f"Лобовые экраны (до {FRONT_SCREEN.max:.0f} мм, шаг {FRONT_SCREEN.step:.0f} мм) снижают пробитие "
        f"кумулятивного до {HEAT_SCREEN_PEN_K * 100:.0f}%, но при максимальной толщине "
        f"уменьшают поворот корпуса на {SCREEN_TURN_LOSS * 100:.0f}%.",
        f"Урон можно менять от {GUN_DAMAGE_RANGE[0] * 100:.0f}% до {GUN_DAMAGE_RANGE[1] * 100:.0f}% номинала калибра, "
        f"пробитие от {GUN_PEN_RANGE[0] * 100:.0f}% до {GUN_PEN_RANGE[1] * 100:.0f}%. "
        "Чем больше любое из них, тем дольше перезарядка.",
        f"Начиная с калибра {HESH_MIN_CAL_MM} мм кумулятивный в слоте 2 можно заменить на HESH.",
        "Стоимость растёт с калибром, бронёй (главным образом лбом), мощностью и тюнингом. "
        "От неё зависит сила врагов.",
    ]

def _td_details():
    return [
        "Орудие без башни наводится только в узком секторе (УГН). Если цель вне сектора, "
        "нужно доворачивать корпус.",
        f"Сектор зависит от калибра: от ±{TD_ARC_MAX_DEG / 2:.0f}° у минимального до "
        f"±{TD_ARC_MIN_DEG / 2:.0f}° у максимального.",
        f"Положение орудия тоже зависит от калибра: до {MOUNT_CAL[0]:.0f} мм оно стоит на лбу, "
        f"от {MOUNT_CAL[1]:.0f} мм уезжает на заднюю опору, между ними плавно смещается к корме.",
        f"Бонус орудия относительно ОБТ того же калибра растёт вместе с калибром: урон {_bonus(TD_GUN.dmg_bonus)}, "
        f"пробитие {_bonus(TD_GUN.pen_bonus)}, скорость снаряда {_bonus(TD_GUN.speed_bonus)}, "
        f"дальность {_bonus(TD_GUN.range_bonus)}.",
        f"Привод наводки медленный: {TD_TRAVERSE_MIN:.0f}–{TD_TRAVERSE_MAX:.0f} °/с в зависимости "
        "от массы орудия и мощности двигателя.",
        f"Скошенный нос: только щучий и только при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм.",
        "Лобовые экраны, тюнинг урона и пробития и спецснаряд настраиваются так же, как у ОБТ.",
    ]

def build():
    col = VEHICLE_ICON_SIZE[0]
    return [
        InfoText("Технику настраивают в Конструкторе: выберите тип кнопкой в левом нижнем углу "
                 "и двигайте ползунки. Характеристики видны на панели справа."),
        InfoText(texts.GUIDE_EXPAND_HINT),
        SectionHeader("Типы техники"),
        AccordionRow(vehicle_icon(VehicleKind.MBT), "ОБТ",
                     "Основной боевой танк. Башня вращается на 360°, поэтому можно ехать в одну сторону "
                     "и стрелять в другую.", _mbt_details(), col_w=col),
        AccordionRow(vehicle_icon(VehicleKind.TD), "ПТ-САУ",
                     "Орудие без башни: наводится только в узком секторе, дальше нужно доворачивать корпус. "
                     "Бьёт сильнее танка того же калибра.", _td_details(), col_w=col),

        SectionHeader("О настройке"),
        InfoText("Чем толще броня и мощнее двигатель, тем тяжелее корпус. "
                 "У ОБТ от тяжести корпуса зависит допустимый калибр."),
        InfoText("Крупный калибр бьёт сильнее, но дольше перезаряжается и стоит дороже. "
                 "Малый калибр слабее, зато снаряд летит дальше."),
        InfoText("Скошенный нос и лобовые экраны усиливают лоб, но делают машину тяжелее. "
                 "От стоимости вашей техники зависит сила врагов."),
    ]