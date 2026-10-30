"""game/content/guide/page_ammo.py — страница инструкции «Снаряды»."""
from combat import RICOCHET_ANGLE, SPLASH_EDGE_K, FRAG_ARMOR_FULL_K, FRAG_ARMOR_ZERO_K
from combat.projectile import RICOCHET_LOSS, RICOCHET_RANGE_K, RICOCHET_MAX
from engine import AmmoKind, PX_PER_M
from inputs import AMMO_HOTKEYS
from ui import SectionHeader, InfoText, AccordionRow
from ui.ammo_icons import make_ammo_icon
from vehicles import AMMO_ORDER, AMMO_TYPES
from vehicles.gun.params import (
    CALIBER, HESH_MIN_CAL_MM, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K, HEAT_MODULE_LOSS_K, HEAT_SCREEN_PEN_K,
    HE_DAMAGE_K, HE_PEN_K, HE_RADIUS_PX_PER_MM, HESH_DAMAGE_K, HESH_PEN_K, HESH_RANGE_K, HESH_RADIUS_PX_PER_MM,
    HESH_STUN_FRAC, HESH_STUN_MIN_S, FRAG_DAMAGE_FRAC
)
from .. import texts
from .common import k as _k

AMMO_ICON_SIZE = (56, 32)
AMMO_COL_W = 72

AMMO_NAMES = {AmmoKind.AP: "Бронебойный", AmmoKind.HEAT: "Кумулятивный",
              AmmoKind.HESH: "HESH (пластичный фугас)", AmmoKind.HE: "Осколочно-фугасный"}

def _pct(k):
    """Множитель -> «+25%» / «-35%»."""
    return f"{(k - 1.0) * 100:+.0f}%"

def _fracs(pair):
    return f"{pair[0] * 100:.0f}–{pair[1] * 100:.0f}%"

def _radius_m(per_mm, cal):
    return per_mm * cal / PX_PER_M

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

def _details():
    import math
    cos_k = 1.0 / math.cos(math.radians(RICOCHET_ANGLE))
    return {
        AmmoKind.AP: [
            "Базовый снаряд: все множители скорости, дальности и перезарядки равны 1, "
            "остальные снаряды считаются относительно него.",
            f"Рикошетит, если угол между траекторией и нормалью брони больше {RICOCHET_ANGLE:.0f}°.",
            f"После рикошета снаряд летит дальше, но теряет {_fracs(RICOCHET_LOSS)} силы (пробитие и урон) "
            f"и {(1 - RICOCHET_RANGE_K) * 100:.0f}% оставшейся дальности. Максимум {RICOCHET_MAX} рикошета на снаряд.",
            "Летит быстрее кумулятивного и HESH, поэтому лучше против движущихся целей и на дальних дистанциях.",
        ],
        AmmoKind.HEAT: [
            f"Относительно бронебойного: пробитие {_pct(HEAT_PEN_K)}, скорость {_pct(HEAT_SPEED_K)}, "
            f"перезарядка {_pct(HEAT_RELOAD_K)}. Урон тот же.",
            f"Не рикошетит. Слишком косой удар считается ровно на границе рикошета: броня для него толще "
            f"примерно в {cos_k:.1f} раза, но пробить её можно.",
            f"Сработав на целой гусенице, теряет пробитие в {HEAT_MODULE_LOSS_K:g} раза больше остальных снарядов, "
            f"на листе лобового экрана остаётся {HEAT_SCREEN_PEN_K * 100:.0f}%. Лента сообщений сообщает о таком срабатывании.",
            "Сбитая гусеница заряд уже не поглощает.",
        ],
        AmmoKind.HESH: [
            f"Доступен от калибра {HESH_MIN_CAL_MM} мм: в Конструкторе заменяет кумулятивный в слоте 2.",
            f"Относительно бронебойного: урон {_pct(HESH_DAMAGE_K)}, пробитие {_pct(HESH_PEN_K)}, "
            f"дальность {HESH_RANGE_K * 100:.0f}% от бронебойного. Скорость и перезарядка как у кумулятивного. Не рикошетит.",
            f"Оглушение при прямом попадании: {_fracs(HESH_STUN_FRAC)} времени перезарядки снаряда (растёт с калибром), "
            f"но не короче {HESH_STUN_MIN_S:g} с. Оглушённая техника не едет и не стреляет, перезарядка стоит.",
            f"Осколки дают {_fracs(FRAG_DAMAGE_FRAC)} урона снаряда (растёт с калибром), "
            f"к краю радиуса урон падает до {SPLASH_EDGE_K * 100:.0f}%.",
            "По цели прямого попадания осколки работают, только если снаряд совсем не пробил броню. "
            "Если пробил хотя бы частично, урон обычный (но не меньше, чем дали бы осколки).",
            f"Осколки ослабляются номинальной бронёй ближайшей грани (без учёта угла): до {FRAG_ARMOR_FULL_K * 100:.0f}% "
            f"пробития снаряда они бьют в полную силу, при {FRAG_ARMOR_ZERO_K * 100:.0f}% и выше урона нет.",
            "Стены и камни закрывают от осколков. При включённом «Уроне по союзникам» осколки ранят и своих.",
        ],
        AmmoKind.HE: [
            f"Относительно бронебойного: урон {_pct(HE_DAMAGE_K)}, пробитие {_pct(HE_PEN_K)}. "
            "Скорость и перезарядка те же. Не рикошетит.",
            "Прямое попадание считается по обычным правилам пробития: гарантированного урона нет.",
            "Если снаряд ничего не задел, он взрывается на пределе дальности и всё равно бьёт осколками.",
            f"Радиус осколков: {_radius_m(HE_RADIUS_PX_PER_MM, 125):.1f} м при 125 мм, "
            f"{_radius_m(HE_RADIUS_PX_PER_MM, CALIBER.max):.1f} м при {CALIBER.max:.0f} мм.",
            f"Осколки дают {_fracs(FRAG_DAMAGE_FRAC)} урона снаряда (растёт с калибром), "
            f"к краю радиуса урон падает до {SPLASH_EDGE_K * 100:.0f}%.",
            "По цели прямого попадания осколки работают, только если снаряд совсем не пробил броню. "
            f"Осколки ослабляются номинальной бронёй ближайшей грани: до {FRAG_ARMOR_FULL_K * 100:.0f}% пробития "
            f"они бьют в полную силу, при {FRAG_ARMOR_ZERO_K * 100:.0f}% и выше урона нет.",
            "Стены и камни закрывают технику за ними от осколков, но сами получают урон. "
            "При включённом «Уроне по союзникам» осколки ранят и своих.",
        ],
    }

def build():
    keys = "/".join(_k(a) for a in AMMO_HOTKEYS)
    texts_by_kind = _texts()
    details = _details()
    items = [
        InfoText(f"Слотов три. Выбор: кнопки справа от сводки танка или клавиши {keys}. "
                 "Тип можно менять прямо в бою."),
        InfoText(texts.GUIDE_EXPAND_HINT),
        SectionHeader("Виды снарядов"),
    ]
    for kind in (*AMMO_ORDER, AmmoKind.HESH):
        title = f"{AMMO_NAMES[kind]} ({AMMO_TYPES[kind].code})"
        items.append(AccordionRow(make_ammo_icon(kind, AMMO_ICON_SIZE), title,
                                  texts_by_kind[kind], details[kind], col_w=AMMO_COL_W))
    return items