"""combat/armor.py — универсальные правила пробития. Одни и те же для стен, танков и любых будущих целей.
Объект сам знает только свою броню (в мм, уже умноженную на его коэффициент);
угол, рикошет и смягчённый урон считаются здесь."""
import math
from dataclasses import dataclass
from typing import Optional

# ==========================================
# ПРАВИЛА
# ==========================================

RICOCHET_ANGLE = 70.0                                   # при угле к нормали больше этого — рикошет
RICOCHET_COS = math.cos(math.radians(RICOCHET_ANGLE))
PIERCE_SPREAD = 0.10                                    # окно ±10% вокруг пробития
NORMALIZATION_MODULE_K = 0.5                            # на экране или гусенице нормализация даёт только эту долю

# ==========================================
# РЕЗУЛЬТАТ ПОПАДАНИЯ
# ==========================================

@dataclass(frozen=True)
class HitResult:
    armor_mm: float                 # исходная броня грани, мм
    eff_armor: Optional[float]      # приведённая броня, мм (None = рикошет)
    damage_frac: float              # доля заявленного урона 0..1

    @property
    def ricochet(self):
        return self.eff_armor is None

# ==========================================
# ФОРМУЛЫ
# ==========================================

def is_ricochet(cos_impact):
    """Рикошетит ли снаряд при таком косинусе угла к нормали грани."""
    return cos_impact < RICOCHET_COS

def effective_armor(armor_mm, cos_impact):
    """Броня с учётом наклона: чем косее удар, тем толще она для снаряда."""
    return armor_mm / max(cos_impact, RICOCHET_COS)

def damage_fraction(penetration, eff_armor):
    """Доля урона 0..1. Ниже окна — 100%, выше — 0%, внутри окна линейно от 100% до 0% (центр = 50%)."""
    if penetration <= 0.0:
        return 0.0
    x = (eff_armor - penetration) / (penetration * PIERCE_SPREAD)   # -1 .. +1 внутри окна
    if x <= -1.0:
        return 1.0
    if x >= 1.0:
        return 0.0
    return 0.5 - 0.5 * x

def resolve_hit(penetration, armor_mm, cos_impact=1.0):
    """Главная функция: любое попадание в любую цель."""
    if is_ricochet(cos_impact):
        return HitResult(armor_mm, None, 0.0)
    eff = effective_armor(armor_mm, cos_impact)
    return HitResult(armor_mm, eff, damage_fraction(penetration, eff))

def normalize_cos(cos_impact, degrees):
    """Косинус угла после доворота к нормали на degrees градусов (угол не уходит ниже 0)."""
    if degrees <= 0.0:
        return cos_impact
    angle = math.degrees(math.acos(min(1.0, max(0.0, cos_impact))))
    return math.cos(math.radians(max(0.0, angle - degrees)))

def _on_module(target, x, y):
    """Попала ли точка (x, y) в целую гусеницу или лобовой экран цели."""
    fn = getattr(target, "module_at", None)
    return fn is not None and fn(x, y) is not None

def impact_cos(stats, cos_impact, target=None, point=None):
    """Косинус угла, который идёт в расчёт урона."""
    if not stats.ricochet:
        cos_impact = max(cos_impact, RICOCHET_COS)
    degrees = stats.normalization_deg
    if degrees > 0.0 and not is_ricochet(cos_impact):
        if target is not None and point is not None and _on_module(target, *point):
            degrees *= 1.0 + NORMALIZATION_MODULE_K
        cos_impact = normalize_cos(cos_impact, degrees)
    return cos_impact

def pen_after_modules(target, penetration, stats, x, y):
    """Пробитие после внешнего модуля цели в точке попадания (x, y)."""
    if stats.module_pen_k >= 1.0 and stats.screen_pen_k >= 1.0:
        return penetration                                    # ББ и ФГ: быстрый выход
    fn = getattr(target, "module_at", None)
    if fn is None:
        return penetration
    module = fn(x, y)
    if module is None:
        return penetration
    k = stats.screen_pen_k if module == "screen" else stats.module_pen_k
    return penetration * k

class Damageable:
    """Миксин для целей."""

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        raise NotImplementedError

    def frag_armor_bonus(self, normal=None):
        """Добавка к броне только для осколков (мм до учёта угла). Цели без экранов: 0."""
        return 0.0

    def frag_damage(self, res, damage, caliber_mm, cos_impact=1.0, normal=None):
        """Урон осколков при НЕпробитии: ceil(урон * калибр / приведённая броня), от 1 до номинала."""
        if res.ricochet or res.eff_armor is None:
            return 0.0
        eff = res.eff_armor
        extra = self.frag_armor_bonus(normal)
        if extra > 0.0:
            eff += effective_armor(extra, cos_impact)
        eff = max(eff, 1.0)
        return float(min(damage, max(1, math.ceil(damage * caliber_mm / eff))))

    def take_hit(self, penetration, damage, cos_impact=1.0, normal=None, min_frac=0.0, caliber_mm=0.0):
        """Попадание снаряда."""
        res = self.hit_result(penetration, cos_impact, normal)
        if res.damage_frac > 0.0 or min_frac <= 0.0:
            dealt = damage * res.damage_frac
        else:
            dealt = self.frag_damage(res, damage, caliber_mm, cos_impact, normal)
        self.hp = max(0.0, self.hp - dealt)
        return dealt

    def take_damage(self, amount):
        """Прямой урон без брони и рикошета (осколки, таран)."""
        self.hp = max(0.0, self.hp - amount)