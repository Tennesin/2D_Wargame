"""vehicles/gun/ammo.py — типы снарядов: таблица множителей и расчёт характеристик выстрела.
Орудие (spec) не меняется: тип снаряда выбирается в бою, а итоговые числа считает ammo_stats.
Это свободная функция, а не метод GunSpec: так тип снаряда остаётся независимым от орудия,
а GunVehicleSpec делегирует в self.gun только явными свойствами."""
from dataclasses import dataclass

from engine import AmmoKind, AmmoStats, clamp, lerp
from vehicles.gun.params import (
    CALIBER,
    HEAT_MODULE_PEN_K, HEAT_SCREEN_PEN_K, HEAT_DAMAGE_K, HEAT_PEN_K, HEAT_SPEED_K, HEAT_RELOAD_K,
    HE_DAMAGE_K, HE_PEN_K, HE_SPEED_K, HE_RELOAD_K, HE_RADIUS_PX_PER_MM,
    HESH_DAMAGE_K, HESH_PEN_K, HESH_SPEED_K, HESH_RELOAD_K, HESH_RANGE_K, HESH_MIN_FRAC,
    HESH_RADIUS_PX_PER_MM, HESH_STUN_FRAC, HESH_STUN_MIN_S, AP_NORMALIZATION_DEG,
    HE_SPLASH_FRAC, HE_SPLASH_ARMOR_REF_MM
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
    range_k: float = 1.0               # множитель дальности относительно ББ
    stun_frac: tuple = (0.0, 0.0)      # оглушение как доля перезарядки снаряда (мин. и макс. калибр); (0, 0) = не оглушает
    stun_min_s: float = 0.0            # нижняя граница длительности оглушения, с
    normalization_deg: tuple = (0.0, 0.0)   # доворот к нормали при мин. и макс. калибре, градусы ((0, 0) = нет)
    splash_frac: tuple = (0.0, 0.0)    # доля урона осколков в центре при мин. и макс. калибре
    splash_armor_ref_mm: float = 0.0   # >0: осколки ослабляются бронёй цели

AMMO_TYPES = {
    AmmoKind.AP: AmmoType(AmmoKind.AP, "ББ", normalization_deg=AP_NORMALIZATION_DEG),
    AmmoKind.HEAT: AmmoType(AmmoKind.HEAT, "КС",
                            dmg_k=HEAT_DAMAGE_K, pen_k=HEAT_PEN_K,
                            speed_k=HEAT_SPEED_K, reload_k=HEAT_RELOAD_K,
                            ricochet=False, module_pen_k=HEAT_MODULE_PEN_K,
                            screen_pen_k=HEAT_SCREEN_PEN_K),
    AmmoKind.HESH: AmmoType(AmmoKind.HESH, "ПФ",
                            dmg_k=HESH_DAMAGE_K, pen_k=HESH_PEN_K,
                            speed_k=HESH_SPEED_K, reload_k=HESH_RELOAD_K,
                            ricochet=False, min_frac=HESH_MIN_FRAC,
                            splash_frac=HESH_MIN_FRAC,
                            radius_px_per_mm=HESH_RADIUS_PX_PER_MM,
                            range_k=HESH_RANGE_K,
                            stun_frac=HESH_STUN_FRAC, stun_min_s=HESH_STUN_MIN_S),
    AmmoKind.HE: AmmoType(AmmoKind.HE, "ФГ",
                          dmg_k=HE_DAMAGE_K, pen_k=HE_PEN_K,
                          speed_k=HE_SPEED_K, reload_k=HE_RELOAD_K,
                          ricochet=False, explode_at_range=True,
                          splash_frac=HE_SPLASH_FRAC,
                          splash_armor_ref_mm=HE_SPLASH_ARMOR_REF_MM,
                          radius_px_per_mm=HE_RADIUS_PX_PER_MM),
}

AMMO_ORDER = (AmmoKind.AP, AmmoKind.HEAT, AmmoKind.HE)   # слоты: ББ, спецснаряд, ФГ

def ammo_kinds(hesh=False):
    """Три снаряда орудия по слотам: во втором HESH заменяет КС."""
    return tuple(AmmoKind.HESH if (k is AmmoKind.HEAT and hesh) else k for k in AMMO_ORDER)

def ammo_stats(spec, kind):
    """Характеристики выстрела орудия spec снарядом kind."""
    t = AMMO_TYPES[kind]
    cal_t = clamp((spec.cal - CALIBER.min) / (CALIBER.max - CALIBER.min), 0.0, 1.0)
    reload = spec.reload * t.reload_k

    stun_s = 0.0
    if t.stun_frac[1] > 0.0:                        # снаряд оглушает: доля растёт с калибром
        stun_s = max(t.stun_min_s, reload * lerp(t.stun_frac[0], t.stun_frac[1], cal_t))

    return AmmoStats(
        kind=kind,
        damage=spec.damage * t.dmg_k,
        penetration=spec.penetration * t.pen_k,
        speed_px=spec.SHELL_SPEED_PX * t.speed_k,
        range_px=spec.SHELL_RANGE_PX * t.range_k,
        reload=reload,
        ricochet=t.ricochet,
        aoe_radius_px=t.radius_px_per_mm * spec.cal,
        min_frac=lerp(t.min_frac[0], t.min_frac[1], cal_t),
        explode_at_range=t.explode_at_range,
        module_pen_k=t.module_pen_k,
        screen_pen_k=t.screen_pen_k,
        stun_s=stun_s,
        caliber_mm=spec.cal,
        normalization_deg=lerp(t.normalization_deg[0], t.normalization_deg[1], cal_t),
        splash_frac=lerp(t.splash_frac[0], t.splash_frac[1], cal_t),
        splash_armor_ref_mm=t.splash_armor_ref_mm,
    )