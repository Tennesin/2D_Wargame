"""game/content/guide/page_enemies.py — страница инструкции «Враги»."""
from ai import ARCHETYPES
from engine import VehicleKind
from ui import SectionHeader, InfoText, IconRow, make_swatch_icon
from ...hud.artillery_warning import RED
from .page_vehicles import vehicle_icon, VEHICLE_ICON_SIZE

ENEMY_TEXTS = {
    "universal": "Сбалансированный противник. Встречается с первого раунда.",
    "scout": "Лёгкий и быстрый, с малым калибром. Заходит с борта и кормы и бьёт издалека.",
    "bunker": "Тяжёлый и медлительный, с очень прочным лбом. Держится лбом к вам.",
    "destroyer": "Мощное орудие и слабая броня по бортам. Держит дистанцию и прячется за укрытиями.",
    "assault": "ПТ-САУ с толстым лбом и острым носом. Лезет в ближний бой.",
    "sniper": "ПТ-САУ с крупным калибром. Стреляет издалека, прячась за укрытиями.",
}

def build():
    col = VEHICLE_ICON_SIZE[0]
    sw = 40
    items = [
        InfoText("Враги появляются группами. Какие типы могут прийти, настраивается в «Новой игре». "
                 "Новые типы открываются по мере роста номера раунда."),
        SectionHeader("Обычные враги"),
    ]
    for key, arch in ARCHETYPES.items():
        if arch.kind is VehicleKind.SPG:
            continue
        items.append(IconRow(make_swatch_icon(arch.color), arch.name,
                             ENEMY_TEXTS.get(key, ""), col_w=sw))

    items += [
        SectionHeader("Артиллерия"),
        IconRow(vehicle_icon(VehicleKind.SPG), "САУ",
                "Хрупкая машина без башни. Стреляет фугасами по дуге издалека, поэтому стены и камни "
                "от неё не защищают. Вплотную не стреляет и пытается отъехать. "
                "Бывает в группах из двух и более врагов.", col_w=col),
        IconRow(make_swatch_icon(RED), "Красный круг",
                "После выстрела на земле появляется красный круг. Четыре треугольника сходятся к центру: "
                "когда они сойдутся, снаряд упадёт. Успейте выехать. Если круг за экраном, "
                "у края показывается указатель с секундами до падения.", col_w=sw),
        InfoText("В центре круга урон полный, и цель оглушается. К краю урон слабеет и режется бронёй. "
                 "Стены разрушаются."),
    ]
    return items