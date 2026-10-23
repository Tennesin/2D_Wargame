"""game/content/guide/page_vehicles.py — страница инструкции «Техника»."""
import pygame

from engine import PX_PER_M, VehicleKind
from ui import SectionHeader, InfoText, IconRow
from vehicles import (
    VEHICLE_TYPES, RENDERERS, make_vehicle, TD_PARAMS, gun_arc_deg,
    NOSE_MIN_FRONT_MM, SUPERHEAVY_MASS_T, WEDGE_ACCEL_K, WEDGE_TURN_K,
)
from world import Camera

VEHICLE_ICON_SIZE = (170, 190)
VEHICLE_ICON_ZOOM_LEVEL = 5          # ступень зума камеры, при которой техника с стволом влезает в иконку
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
    cal = TD_PARAMS["gun_caliber_mm"]
    wide = gun_arc_deg(cal.min) / 2.0
    narrow = gun_arc_deg(cal.max) / 2.0
    col = VEHICLE_ICON_SIZE[0]
    return [
        InfoText("Технику настраивают в Конструкторе: выберите тип кнопкой в левом нижнем углу, "
                 "затем крутите ползунки. Расчётные характеристики видны на панели справа."),
        SectionHeader("Типы техники"),
        IconRow(vehicle_icon(VehicleKind.MBT), "ОБТ — основной боевой танк",
                "Башня вращается на 360°, поэтому можно ехать в одну сторону и стрелять в другую. "
                "Класс корпуса (лёгкий, средний, тяжёлый) зависит от брони и мощности двигателя: "
                "чем тяжелее корпус, тем крупнее допустимый калибр.", col_w=col),
        IconRow(vehicle_icon(VehicleKind.TD), "ПТ-САУ",
                f"Орудие без башни: наводка только в пределах сектора (от ±{wide:.0f}° у малых калибров "
                f"до ±{narrow:.0f}° у крупных), дальше нужно доворачивать корпус. Урон и пробитие выше, чем у "
                "ОБТ того же калибра. Чем крупнее калибр, тем дальше назад уезжает орудие.", col_w=col),

        SectionHeader("Нос и экраны"),
        InfoText(f"Щучий нос (двускатный лоб) открывается при лобовой броне больше {NOSE_MIN_FRONT_MM:.0f} мм. "
                 f"У ОБТ тяжелее {SUPERHEAVY_MASS_T:.0f} т он превращается в клин. Платой за это становятся "
                 f"хуже разгон (на {(1 - WEDGE_ACCEL_K) * 100:.0f}%) и поворот корпуса "
                 f"(на {(1 - WEDGE_TURN_K) * 100:.0f}%)."),
        InfoText("Лобовые экраны — тонкие листы перед лбом. Кумулятивный снаряд срабатывает на них "
                 "и теряет пробитие, но только при попадании прямо в лист, а не в просвет между листами."),
    ]