"""content/guide/page_ammo.py — страница инструкции «Снаряды»."""
from engine import PX_PER_M, AmmoKind
from combat import RICOCHET_ANGLE
from inputs import AMMO_HOTKEYS
from ui import SectionHeader, InfoText, IconRow
from ui.ammo_icons import make_ammo_icon
from vehicles import AMMO_ORDER, AMMO_TYPES
from vehicles.gun_params import (
    CALIBER, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K, HEAT_MODULE_PEN_K, HEAT_SCREEN_PEN_K,
    HE_DAMAGE_K, HE_PEN_K, HE_MIN_FRAC, HE_RADIUS_PX_PER_MM, HESH_MIN_CAL_MM, HESH_DAMAGE_K,
    HESH_PEN_K, HESH_RANGE_K, HESH_STUN_S
)
from .common import k as _k

AMMO_ICON_SIZE = (56, 32)
AMMO_COL_W = 72

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

def build():
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