"""vehicles/ammo.py — типы снарядов: таблица множителей и расчёт характеристик выстрела.
Орудие (spec) не меняется: тип снаряда выбирается в бою, а итоговые числа считает ammo_stats.
Это свободная функция, а не метод GunSpec: TankSpec копирует только атрибуты GunSpec
(self.__dict__.update(vars(self.gun))), методы до него не доходят."""
from dataclasses import dataclass

from engine import AmmoKind, AmmoStats, clamp, lerp
from vehicles.gun.params import (
    CALIBER,
    HEAT_MODULE_PEN_K, HEAT_SCREEN_PEN_K, HEAT_DAMAGE_K, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K,
    HE_DAMAGE_K, HE_PEN_K, HE_SPEED_K, HE_RELOAD_K, HE_MIN_FRAC, HE_RADIUS_PX_PER_MM, HESH_STUN_S,
    HESH_DAMAGE_K, HESH_PEN_K, HESH_SPEED_K, HESH_RELOAD_K, HESH_RANGE_K, HESH_MIN_FRAC,
)

SPECIAL_HEAT = "heat"      # значения переключателя «спецснаряд» в конструкторе
SPECIAL_HESH = "hesh"

@dataclass(frozen=True)
class AmmoType:
    kind: AmmoKind
    code: str                          # двухбуквенная подпись на кнопке
    dmg_k: float = 1.0
    pen_k: float = 1.0
    speed_k: float = 1.0
    reload_k: float = 1.0
    ricochet: bool = True
    explode_at_range: bool = False
    min_frac: tuple = (0.0, 0.0)
    radius_px_per_mm: float = 0.0
    module_pen_k: float = 1.0
    screen_pen_k: float = 1.0
    range_k: float = 1.0  # множитель дальности относительно ББ
    stun_s: float = 0.0

AMMO_TYPES = {
    AmmoKind.AP: AmmoType(AmmoKind.AP, "ББ"),
    AmmoKind.HEAT: AmmoType(AmmoKind.HEAT, "КС",
                            dmg_k=HEAT_DAMAGE_K, pen_k=HEAT_PEN_K,
                            speed_k=HEAT_SPEED_K, reload_k=HEAT_RELOAD_K,
                            ricochet=False, module_pen_k=HEAT_MODULE_PEN_K,
                            screen_pen_k=HEAT_SCREEN_PEN_K),
    AmmoKind.HESH: AmmoType(AmmoKind.HESH, "ПФ",
                        dmg_k=HESH_DAMAGE_K, pen_k=HESH_PEN_K,
                        speed_k=HESH_SPEED_K, reload_k=HESH_RELOAD_K,
                        ricochet=False, min_frac=HESH_MIN_FRAC,
                        range_k=HESH_RANGE_K, stun_s=HESH_STUN_S),
    AmmoKind.HE: AmmoType(AmmoKind.HE, "ФГ",
                          dmg_k=HE_DAMAGE_K, pen_k=HE_PEN_K,
                          speed_k=HE_SPEED_K, reload_k=HE_RELOAD_K,
                          ricochet=False, explode_at_range=True,
                          min_frac=HE_MIN_FRAC, radius_px_per_mm=HE_RADIUS_PX_PER_MM),
}

AMMO_ORDER = (AmmoKind.AP, AmmoKind.HEAT, AmmoKind.HE)   # слоты: ББ, спецснаряд, ФГ

def ammo_kinds(hesh=False):
    """Три снаряда орудия по слотам: во втором HESH заменяет КС."""
    return tuple(AmmoKind.HESH if (k is AmmoKind.HEAT and hesh) else k for k in AMMO_ORDER)

def ammo_stats(spec, kind):
    """Характеристики выстрела орудия spec снарядом kind."""
    t = AMMO_TYPES[kind]
    cal_t = clamp((spec.cal - CALIBER.min) / (CALIBER.max - CALIBER.min), 0.0, 1.0)
    return AmmoStats(
        kind=kind,
        damage=spec.damage * t.dmg_k,
        penetration=spec.penetration * t.pen_k,
        speed_px=spec.SHELL_SPEED_PX * t.speed_k,
        range_px=spec.SHELL_RANGE_PX * t.range_k,
        reload=spec.reload * t.reload_k,
        ricochet=t.ricochet,
        aoe_radius_px=t.radius_px_per_mm * spec.cal,
        min_frac=lerp(t.min_frac[0], t.min_frac[1], cal_t),
        explode_at_range=t.explode_at_range,
        module_pen_k=t.module_pen_k,
        screen_pen_k=t.screen_pen_k,
        stun_s=t.stun_s,
        caliber_mm=spec.cal,
    )