"""vehicles/ammo.py — типы снарядов: таблица множителей и расчёт характеристик выстрела.
Орудие (spec) не меняется: тип снаряда выбирается в бою, а итоговые числа считает ammo_stats.
Это свободная функция, а не метод GunSpec: TankSpec копирует только атрибуты GunSpec
(self.__dict__.update(vars(self.gun))), методы до него не доходят."""
from dataclasses import dataclass

from engine import AmmoKind, AmmoStats, clamp, lerp
from .gun_params import (
    CALIBER,
    HEAT_DAMAGE_K, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K,
    HE_DAMAGE_K, HE_PEN_K, HE_SPEED_K, HE_RELOAD_K, HE_MIN_FRAC, HE_RADIUS_PX_PER_MM,
)

@dataclass(frozen=True)
class AmmoType:
    kind: AmmoKind
    code: str                          # двухбуквенная подпись на кнопке
    name: str
    dmg_k: float = 1.0
    pen_k: float = 1.0
    speed_k: float = 1.0
    reload_k: float = 1.0
    ricochet: bool = True
    explode_at_range: bool = False
    min_frac: tuple = (0.0, 0.0)       # гарантированная доля урона при мин. и макс. калибре
    radius_px_per_mm: float = 0.0      # радиус взрыва на 1 мм калибра (0 = нет взрыва)

AMMO_TYPES = {
    AmmoKind.AP: AmmoType(AmmoKind.AP, "ББ", "Бронебойный"),
    AmmoKind.HEAT: AmmoType(AmmoKind.HEAT, "КС", "Кумулятивный",
                            dmg_k=HEAT_DAMAGE_K, pen_k=HEAT_PEN_K,
                            speed_k=HEAT_SPEED_K, reload_k=HEAT_RELOAD_K,
                            ricochet=False),
    AmmoKind.HE: AmmoType(AmmoKind.HE, "ФГ", "Фугасный",
                          dmg_k=HE_DAMAGE_K, pen_k=HE_PEN_K,
                          speed_k=HE_SPEED_K, reload_k=HE_RELOAD_K,
                          ricochet=False, explode_at_range=True,
                          min_frac=HE_MIN_FRAC, radius_px_per_mm=HE_RADIUS_PX_PER_MM),
}

AMMO_ORDER = tuple(AMMO_TYPES)         # порядок кнопок и горячих клавиш: ББ, КС, ФГ

def ammo_stats(spec, kind):
    """Характеристики выстрела орудия spec снарядом kind."""
    t = AMMO_TYPES[kind]
    cal_t = clamp((spec.cal - CALIBER.min) / (CALIBER.max - CALIBER.min), 0.0, 1.0)
    return AmmoStats(
        kind=kind,
        damage=spec.damage * t.dmg_k,
        penetration=spec.penetration * t.pen_k,
        speed_px=spec.SHELL_SPEED_PX * t.speed_k,     # после множителя не зажимаем: иначе КС потеряет замедление
        range_px=spec.SHELL_RANGE_PX,                 # дальность одна на все типы
        reload=spec.reload * t.reload_k,
        ricochet=t.ricochet,
        aoe_radius_px=t.radius_px_per_mm * spec.cal,
        min_frac=lerp(t.min_frac[0], t.min_frac[1], cal_t),
        explode_at_range=t.explode_at_range,
    )