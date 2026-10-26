"""game/content/guide/page_vehicles.py — страница инструкции «Техника»."""
import pygame

from engine import PX_PER_M, VehicleKind
from ui import SectionHeader, InfoText, IconRow
from vehicles import VEHICLE_TYPES, RENDERERS, make_vehicle
from world import Camera

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

def build():
    col = VEHICLE_ICON_SIZE[0]
    return [
        InfoText("Технику настраивают в Конструкторе: выберите тип кнопкой в левом нижнем углу "
                 "и двигайте ползунки. Характеристики видны на панели справа."),
        SectionHeader("Типы техники"),
        IconRow(vehicle_icon(VehicleKind.MBT), "ОБТ",
                "Основной боевой танк. Башня вращается на 360°, поэтому можно ехать в одну сторону "
                "и стрелять в другую.", col_w=col),
        IconRow(vehicle_icon(VehicleKind.TD), "ПТ-САУ",
                "Орудие без башни: наводится только в узком секторе, дальше нужно доворачивать корпус. "
                "Бьёт сильнее танка того же калибра.", col_w=col),

        SectionHeader("О настройке"),
        InfoText("Чем толще броня и мощнее двигатель, тем тяжелее корпус. "
                 "У ОБТ от тяжести корпуса зависит допустимый калибр."),
        InfoText("Крупный калибр бьёт сильнее, но дольше перезаряжается и стоит дороже. "
                 "Малый калибр слабее, зато снаряд летит дальше."),
        InfoText("Скошенный нос и лобовые экраны усиливают лоб, но делают машину тяжелее. "
                 "От стоимости вашей техники зависит сила врагов."),
    ]