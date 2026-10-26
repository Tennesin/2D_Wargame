"""game/content/guide/page_ammo.py — страница инструкции «Снаряды»."""
from engine import AmmoKind
from inputs import AMMO_HOTKEYS
from ui import SectionHeader, InfoText, IconRow
from ui.ammo_icons import make_ammo_icon
from vehicles import AMMO_ORDER, AMMO_TYPES
from vehicles.gun.params import HESH_MIN_CAL_MM
from .common import k as _k

AMMO_ICON_SIZE = (56, 32)
AMMO_COL_W = 72

AMMO_NAMES = {AmmoKind.AP: "Бронебойный", AmmoKind.HEAT: "Кумулятивный",
              AmmoKind.HESH: "HESH (пластичный фугас)", AmmoKind.HE: "Осколочно-фугасный"}

def _texts():
    return {
        AmmoKind.AP:
            "Быстрый и точный снаряд. Под слишком острым углом рикошетит.",
        AmmoKind.HEAT:
            "Пробивает лучше бронебойного, но летит медленнее и дольше перезаряжается. "
            "Не рикошетит. Теряет пробитие, если сработает на гусенице или лобовом экране.",
        AmmoKind.HESH:
            f"Заменяет кумулятивный при калибре от {HESH_MIN_CAL_MM} мм (выбирается в Конструкторе). "
            "Бьёт осколками по площади и наносит урон даже без пробития. "
            "Прямое попадание оглушает цель: она не может ехать и стрелять.",
        AmmoKind.HE:
            "Бьёт осколками по площади и наносит урон даже без пробития, но броню почти не пробивает. "
            "Стены и камни закрывают от осколков.",
    }

def build():
    keys = "/".join(_k(a) for a in AMMO_HOTKEYS)
    texts = _texts()
    items = [
        InfoText(f"Слотов три. Выбор: кнопки справа от сводки танка или клавиши {keys}. "
                 "Тип можно менять прямо в бою."),
        SectionHeader("Виды снарядов"),
    ]
    for kind in (*AMMO_ORDER, AmmoKind.HESH):
        title = f"{AMMO_NAMES[kind]} ({AMMO_TYPES[kind].code})"
        items.append(IconRow(make_ammo_icon(kind, AMMO_ICON_SIZE), title, texts[kind], col_w=AMMO_COL_W))
    return items