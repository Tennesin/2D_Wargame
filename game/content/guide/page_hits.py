"""game/content/guide/page_hits.py — страница инструкции «Попадания»."""
import math

from combat import RICOCHET_ANGLE
from combat.aim import C_YES, C_CHANCE, C_NO
from combat.armor import PIERCE_SPREAD
from combat.ram import ZONE_K
from inputs import Action
from ui import SectionHeader, InfoText, IconRow, make_swatch_icon
from vehicles import TRACKS
from vehicles.chassis.params import TRACK_REPAIR_S, ONE_TRACK_SPEED_K
from .common import k as _k

def build():
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