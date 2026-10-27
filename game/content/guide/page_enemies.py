"""game/content/guide/page_enemies.py — страница инструкции «Враги»."""
from ai import ARCHETYPES
from ai.artillery_brain import SCATTER_K
from engine import VehicleKind
from ui import SectionHeader, InfoText, AccordionRow, make_swatch_icon
from vehicles import NOSE_FLAT, NOSE_RU, SPG_PARAMS
from vehicles.spg.params import (SPG_RANGE_M, SPG_DEAD_K, SPG_RELOAD_S, SPG_HP_MIN, SPG_HP_MAX,
                                 SPG_INNER_K, SPG_EDGE_K, SPG_WALL_K, SPG_ARMOR_REF_MM, SPG_STUN_REF_S)
from ...hud.artillery_warning import RED
from ...match.rounds.schedule import UNLOCKS
from .. import texts
from .page_vehicles import vehicle_icon, VEHICLE_ICON_SIZE

ENEMY_TEXTS = {
    "universal": "Сбалансированный противник. Встречается с первого раунда.",
    "scout": "Лёгкий и быстрый, с малым калибром. Заходит с борта и кормы и бьёт издалека.",
    "bunker": "Тяжёлый и медлительный, с очень прочным лбом. Держится лбом к вам.",
    "destroyer": "Мощное орудие и слабая броня по бортам. Держит дистанцию и прячется за укрытиями.",
    "assault": "ПТ-САУ с толстым лбом и острым носом. Лезет в ближний бой.",
    "sniper": "ПТ-САУ с крупным калибром. Стреляет издалека, прячась за укрытиями.",
}

UNLOCK_ROUND = {key: n for n, key in UNLOCKS}

def _details(key, arch):
    """Подробности архетипа из его же полей (чтобы текст не расходился с балансом)."""
    rows = [f"Желаемая дистанция боя: около {arch.engage_dist_m:.0f} м."]
    if arch.kind is VehicleKind.TD:
        rows.append("ПТ-САУ: орудие без башни, поэтому ему приходится доворачивать корпус на цель.")
    if arch.retreat_hp > 0.0:
        rows.append(f"Ищет укрытие, когда здоровье ниже {arch.retreat_hp * 100:.0f}%.")
    if arch.cover_bias >= 0.5:
        rows.append("Часто прячется за камнями и стенами и выходит, когда вы смотрите в другую сторону.")
    if arch.standoff:
        rows.append("Дальнобойный: держит дистанцию и ищет огневую позицию с чистой линией огня.")
    if arch.flank_bias >= 0.5:
        rows.append("Охотно обходит вас, если лоб не пробивается.")
    if arch.aspect_drive > 0.0 and arch.aspect_deg >= 120.0:
        rows.append("Стремится зайти вам в борт и корму.")
    elif arch.aspect_drive > 0.0 and arch.aspect_deg <= 10.0:
        rows.append("Старается держаться к вам лбом.")
    caps = arch.caps
    rows.append(f"Потолок сборки: калибр до {caps['gun_caliber_mm']} мм, лоб до {caps['front_armor_mm']} мм, "
                f"борт до {caps['side_armor_mm']} мм, корма до {caps['rear_armor_mm']} мм.")
    if arch.nose != NOSE_FLAT:
        rows.append(f"Нос корпуса: {NOSE_RU[arch.nose]}.")
    if arch.screen_mm[1] > 0.0:
        rows.append(f"Лобовые экраны {arch.screen_mm[0]:.0f}–{arch.screen_mm[1]:.0f} мм.")
    if key in UNLOCK_ROUND:
        rows.append(f"Открывается с раунда {UNLOCK_ROUND[key]}. Против сильно «выкрученной» техники игрока "
                    "может появиться раньше.")
    return rows

def _sau_details():
    cal = SPG_PARAMS["gun_caliber_mm"]
    return [
        f"Калибр {cal.min:.0f}–{cal.max:.0f} мм. От него зависят дальность ({SPG_RANGE_M[0]:.0f}–{SPG_RANGE_M[1]:.0f} м), "
        f"перезарядка ({SPG_RELOAD_S[0]:.0f}–{SPG_RELOAD_S[1]:.0f} с), радиус взрыва и урон.",
        f"Мёртвая зона: ближе {SPG_DEAD_K * 100:.0f}% своей дальности САУ не стреляет и пытается отъехать.",
        f"Здоровья мало: {SPG_HP_MIN}–{SPG_HP_MAX} HP, броня не больше {SPG_PARAMS['front_armor_mm'].max:.0f} мм.",
        "Орудие без башни: сектор наводки узкий, корпус САУ доворачивает сама.",
        f"Целится по упреждённой точке. Снаряд ложится с разбросом около {SCATTER_K * 100:.0f}% дистанции.",
        "Не стреляет, если взрыв заденет союзника (при включённом «Уроне по союзникам»).",
        "Бывает в группах из двух и более врагов.",
    ]

def _circle_details():
    return [
        "Внешний круг — граница взрыва. Четыре треугольника сходятся к центру: когда они сойдутся, снаряд упадёт.",
        f"Внутренний круг (зона максимума) составляет {SPG_INNER_K * 100:.0f}% внешнего. "
        f"Там урон полный, броня не учитывается, цель оглушается (около {SPG_STUN_REF_S:g} с у эталонного калибра).",
        f"В кольце урон падает до {SPG_EDGE_K * 100:.0f}% на границе и режется бронёй: чем она толще, тем слабее удар "
        f"(опорная броня {SPG_ARMOR_REF_MM:.0f} мм).",
        f"Стены получают ×{SPG_WALL_K:g} урона и разрушаются. Камни и стены от взрыва не защищают.",
        "Если круг за экраном, у края показывается указатель с секундами до падения.",
    ]

def build():
    col = VEHICLE_ICON_SIZE[0]
    sw = 40
    items = [
        InfoText("Враги появляются группами. Какие типы могут прийти, настраивается в «Новой игре». "
                 "Новые типы открываются по мере роста номера раунда."),
        InfoText(texts.GUIDE_EXPAND_HINT),
        SectionHeader("Обычные враги"),
    ]
    for key, arch in ARCHETYPES.items():
        if arch.kind is VehicleKind.SPG:
            continue
        items.append(AccordionRow(make_swatch_icon(arch.color), arch.name,
                                  ENEMY_TEXTS.get(key, ""), _details(key, arch), col_w=sw))

    items += [
        SectionHeader("Артиллерия"),
        AccordionRow(vehicle_icon(VehicleKind.SPG), "САУ",
                     "Хрупкая машина без башни. Стреляет фугасами по дуге издалека, поэтому стены и камни "
                     "от неё не защищают. Вплотную не стреляет и пытается отъехать.",
                     _sau_details(), col_w=col),
        AccordionRow(make_swatch_icon(RED), "Красный круг",
                     "После выстрела на земле появляется красный круг. Успейте выехать, пока треугольники "
                     "не сошлись к центру.", _circle_details(), col_w=sw),
        InfoText("В центре круга урон полный, и цель оглушается. К краю урон слабеет и режется бронёй. "
                 "Стены разрушаются."),
    ]
    return items