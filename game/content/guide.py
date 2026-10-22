"""game/guide.py — содержимое страниц инструкции. Единственное место, где инструкция «знакомится»
с клавишами, снарядами и техникой. Клавиши берутся из inputs.key_label, числа из констант,
поэтому текст не устаревает при смене баланса или привязок.
Страница = функция без аргументов, возвращающая список блоков (см. PAGES внизу)."""
import math

import pygame

from combat import RICOCHET_ANGLE
from combat.aim import C_YES, C_CHANCE, C_NO
from combat.armor import PIERCE_SPREAD
from combat.ram import ZONE_K
from engine import PX_PER_M, AmmoKind, VehicleKind
from inputs import Action, AMMO_HOTKEYS, key_label
from structures import ROTATE_SNAP_DEG
from ui import SectionHeader, InfoText, IconRow, KeyRow, make_mouse_icon, make_swatch_icon
from ui.ammo_icons import make_ammo_icon
from vehicles import (
    VEHICLE_TYPES, RENDERERS, make_vehicle, AMMO_ORDER, AMMO_TYPES, TD_PARAMS, gun_arc_deg,
    NOSE_MIN_FRONT_MM, SUPERHEAVY_MASS_T, WEDGE_ACCEL_K, WEDGE_TURN_K, TRACKS,
)
from vehicles.chassis_params import TRACK_REPAIR_S, ONE_TRACK_SPEED_K
from vehicles.gun_params import (
    CALIBER, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K, HEAT_MODULE_PEN_K, HEAT_SCREEN_PEN_K,
    HE_DAMAGE_K, HE_PEN_K, HE_MIN_FRAC, HE_RADIUS_PX_PER_MM, HESH_MIN_CAL_MM, HESH_DAMAGE_K,
    HESH_PEN_K, HESH_RANGE_K, HESH_STUN_S
)
from world import Camera
from ..config import COMBAT_HOLD

AMMO_ICON_SIZE = (56, 32)
AMMO_COL_W = 72

VEHICLE_ICON_SIZE = (170, 190)
VEHICLE_ICON_ZOOM_LEVEL = 5          # ступень зума камеры, при которой техника с стволом влезает в иконку
VEHICLE_ICON_CENTER_Y = -180.0       # камера чуть выше центра танка: ствол смотрит вверх
VEHICLE_ICON_BG = (36, 40, 46)

def _k(action):
    return key_label(action)

# ==========================================
# СТРАНИЦА 1. УПРАВЛЕНИЕ
# ==========================================
def _controls():
    combat_text = ("Боевой режим, пока клавиша зажата: появляется красная линия прицела и работает огонь."
                   if COMBAT_HOLD else
                   "Включить или выключить боевой режим: появляется красная линия прицела и работает огонь.")
    return [
        SectionHeader("Движение и прицел"),
        KeyRow([_k(Action.FORWARD), _k(Action.LEFT), _k(Action.BACKWARD), _k(Action.RIGHT)],
               "Движение корпуса: вперёд, влево, назад, вправо. Стрелки работают так же."),
        KeyRow([make_mouse_icon()],
               "Орудие следит за курсором. Если навести курсор на танк, стену или камень, "
               "появится краткая сводка."),
        KeyRow([_k(Action.LOCK_TURRET)],
               "Зафиксировать башню в текущем положении или снова отпустить."),

        SectionHeader("Бой"),
        KeyRow([_k(Action.COMBAT)], combat_text),
        KeyRow([make_mouse_icon("left")],
               "Выстрел. Работает только в боевом режиме; удерживайте кнопку для стрельбы по готовности."),
        KeyRow([_k(a) for a in AMMO_HOTKEYS],
               "Выбор снаряда: бронебойный, спецснаряд (кумулятивный или HESH), фугасный. "
               "То же делают кнопки справа от сводки танка."),
        KeyRow([_k(Action.REPAIR)],
               f"Ремонт сбитой гусеницы: {TRACK_REPAIR_S:.0f} с на гусеницу, по одной за раз."),

        SectionHeader("Камера"),
        KeyRow([make_mouse_icon("wheel")],
               "Колёсико мыши приближает и отдаляет вид. Клавиши + и − (PgUp, PgDn) делают то же."),
        KeyRow([make_mouse_icon()],
               "Камера плавно смещается к курсору: подведите мышь к краю экрана, чтобы заглянуть вперёд. "
               "Пока курсор у центра, камера стоит на танке."),
        KeyRow([_k(Action.TOGGLE_FREE_CAM), make_mouse_icon("right")],
               "Свободная камера: правая кнопка с перетаскиванием двигает вид. Повторное нажатие возвращает камеру к танку."),

        SectionHeader("Стены"),
        KeyRow([_k(Action.TOGGLE_BUILD)],
               "Режим стройки. Левая кнопка мыши ставит стену, правая выходит из режима. Танком в это время не управляют."),
        KeyRow([make_mouse_icon("left")],
               "Клик по стене выбирает её и открывает панель настроек. Белая точка в центре стены поворачивает её; "
               f"с Shift поворот идёт шагом {ROTATE_SNAP_DEG:.0f}°."),
        KeyRow([_k(Action.DELETE_WALL)], "Удалить выбранную стену."),

        SectionHeader("Прочее"),
        KeyRow([_k(Action.TOGGLE_DEBUG)], "Отладочная информация: FPS, координаты, сведения о ботах."),
        KeyRow([_k(Action.CANCEL)],
               "Закрывает по одному слою: стройку или панель стены, затем боевой режим, а потом выходит в меню."),
    ]

# ==========================================
# СТРАНИЦА 2. СНАРЯДЫ
# ==========================================
AMMO_NAMES = {AmmoKind.AP: "Бронебойный", AmmoKind.HEAT: "Кумулятивный",
              AmmoKind.HESH: "HESH (пластичный фугас)", AmmoKind.HE: "Осколочно-фугасный"}

def _ammo_texts():
    cal = CALIBER.default
    radius_m = HE_RADIUS_PX_PER_MM * cal / PX_PER_M
    return {
        AmmoKind.AP:
            "Стандартный снаряд: быстрый и точный. При слишком косом попадании "
            f"(угол больше {RICOCHET_ANGLE:.0f}°) рикошетит и летит дальше с потерей силы.",
        AmmoKind.HEAT:
            f"Пробитие выше на {(HEAT_PEN_K - 1) * 100:.0f}% при том же уроне, но снаряд летит медленнее "
            f"(скорость ×{HEAT_SPEED_K:g}) и перезаряжается дольше (×{HEAT_RELOAD_K:g}). Не рикошетит. "
            f"Чувствителен к экранам: сработав на гусенице, теряет пробитие (×{HEAT_MODULE_PEN_K:g}), "
            f"на лобовом экране (×{HEAT_SCREEN_PEN_K:g}).",
        AmmoKind.HESH:
            f"Заменяет кумулятивный при калибре от {HESH_MIN_CAL_MM} мм (переключатель в Конструкторе). "
            f"Урон выше на {(HESH_DAMAGE_K - 1) * 100:.0f}%, пробитие ниже на {(1 - HESH_PEN_K) * 100:.0f}%, "
            f"дальность {HESH_RANGE_K * 100:.0f}% от бронебойного. Не рикошетит и даже без пробития наносит "
            f"осколками часть урона. Прямое попадание оглушает цель на {HESH_STUN_S:g} с: она не может "
            "двигаться, а её перезарядка стоит.",
        AmmoKind.HE:
            f"Взрывной снаряд: урон выше на {(HE_DAMAGE_K - 1) * 100:.0f}%, но пробитие всего "
            f"{HE_PEN_K * 100:.0f}% от бронебойного. Взрывается и бьёт по области (около {radius_m:.1f} м "
            f"при калибре {cal:.0f} мм). Даже без пробития гарантированно наносит осколками "
            f"{HE_MIN_FRAC[0] * 100:.0f}-{HE_MIN_FRAC[1] * 100:.0f}% урона. Долетев до предела дальности, "
            "взрывается в воздухе.",
    }

def _ammo():
    keys = "/".join(_k(a) for a in AMMO_HOTKEYS)
    texts = _ammo_texts()
    items = [
        InfoText(f"Есть три слота снарядов. Выбор: кнопки справа от сводки танка или клавиши {keys}. "
                 "Во втором слоте стоит кумулятивный, а при калибре от "
                 f"{HESH_MIN_CAL_MM} мм его можно заменить на HESH в Конструкторе. "
                 "Тип можно менять в бою, прогресс перезарядки при этом сохраняется пропорционально."),
        SectionHeader("Виды снарядов"),
    ]
    for kind in (*AMMO_ORDER, AmmoKind.HESH):
        title = f"{AMMO_NAMES[kind]} ({AMMO_TYPES[kind].code})"
        items.append(IconRow(make_ammo_icon(kind, AMMO_ICON_SIZE), title, texts[kind], col_w=AMMO_COL_W))
    return items

# ==========================================
# СТРАНИЦА 3. ПОПАДАНИЯ И БРОНЯ
# ==========================================
def _hits():
    cos_k = 1.0 / math.cos(math.radians(RICOCHET_ANGLE))
    spread = PIERCE_SPREAD * 100.0
    sw = 40
    return [
        InfoText("Каждое попадание сравнивает пробитие снаряда с приведённой бронёй цели. "
                 "Линия прицела в боевом режиме заранее показывает результат."),
        SectionHeader("Цвета подписи у линии прицела"),
        IconRow(make_swatch_icon(C_YES), "Урон: 100%",
                "Пробитие заметно выше приведённой брони: снаряд наносит полный урон.", col_w=sw),
        IconRow(make_swatch_icon(C_CHANCE), "Урон ослаблен",
                f"Пробитие и броня почти равны (в пределах ±{spread:.0f}%): урон плавно падает от 100% до 0%. "
                "Так же показываются осколки фугаса.", col_w=sw),
        IconRow(make_swatch_icon(C_NO), "Не пробито или рикошет",
                "Урона нет. Попробуйте другой снаряд, другую грань цели или другой угол.", col_w=sw),

        SectionHeader("Угол и грани"),
        InfoText("Чем косее удар, тем толще броня для снаряда: приведённая броня = броня / cos угла. "
                 f"При угле больше {RICOCHET_ANGLE:.0f}° бронебойный снаряд рикошетит. Кумулятивный и фугасный "
                 f"не рикошетят, но на таком угле броня для них толще примерно в {cos_k:.1f} раза."),
        InfoText("У техники три грани: лоб, борт и корма, у каждой своя броня (ползунки в Конструкторе). "
                 f"Гусеница закрывает борт и добавляет к нему {TRACKS.armor_mm:.0f} мм. "
                 "Как правило, выгоднее целиться в борт и корму."),

        SectionHeader("Гусеницы"),
        InfoText("Попадание в передний или задний край гусеницы сбивает её. С одной сбитой гусеницей машина "
                 f"ползёт по дуге (тяга ×{ONE_TRACK_SPEED_K:g}), с двумя стоит на месте. "
                 f"Ремонт ({_k(Action.REPAIR)}): {TRACK_REPAIR_S:.0f} с на гусеницу, только по одной."),

        SectionHeader("Таран"),
        InfoText("Удар о камень или танк толкает обоих. Лёгкие камни можно сдвинуть, тяжёлые остаются на месте. "
                 "Танки получают урон от потери скорости при ударе, а грань решает многое: "
                 f"лоб страдает меньше всего (×{ZONE_K['front']:g}), борт ×{ZONE_K['side']:g}, "
                 f"корма больше всего (×{ZONE_K['rear']:g})."),
    ]

# ==========================================
# СТРАНИЦА 4. ТЕХНИКА
# ==========================================
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

def _vehicles():
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

# ==========================================
# СПИСОК СТРАНИЦ
# ==========================================
# (подпись вкладки, функция-сборщик). Чтобы добавить страницу, допишите сюда строку.
PAGES = [
    ("Управление", _controls),
    ("Снаряды", _ammo),
    ("Попадания", _hits),
    ("Техника", _vehicles),
]

def build_page(index):
    """Свежий список блоков страницы с номером index."""
    return PAGES[index][1]()