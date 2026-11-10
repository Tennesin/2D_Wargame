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
FRAG_ARMOR_FULL_K = 1.10                                # номинальная броня до 110% пробития: осколки в полную силу
FRAG_ARMOR_ZERO_K = 2.20                                # от 220% пробития и выше: осколков нет

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

def frag_armor_factor(armor_mm, penetration):
    """Множитель осколков 0..1 по номинальной броне и пробитию снаряда."""
    if penetration <= 0.0:
        return 0.0
    ratio = armor_mm / penetration
    if ratio <= FRAG_ARMOR_FULL_K:
        return 1.0
    if ratio >= FRAG_ARMOR_ZERO_K:
        return 0.0
    return (FRAG_ARMOR_ZERO_K - ratio) / (FRAG_ARMOR_ZERO_K - FRAG_ARMOR_FULL_K)

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

@dataclass(frozen=True)
class ModuleHit:
    module: Optional[str]           # "left" / "right" / None (гусеница)
    pen: float                      # пробитие после экранов и гусеницы
    track_damage: float = 0.0       # урон гусенице, HP её шкалы
    screen_lost: float = 0.0        # сколько пробития съели экраны, мм
    track_lost: float = 0.0         # сколько съела гусеница, мм

def module_hit(target, penetration, damage, stats, cos_impact, x, y, dx=None, dy=None):
    """Что делают внешние модули."""
    pen, screen_lost = penetration, 0.0
    along = getattr(target, "screens_along_world", None)
    if along is not None and dx is not None:
        for mm, cos in along(x, y, dx, dy):
            if pen <= 0.0:
                break
            loss = min(pen, effective_armor(mm, cos) * stats.screen_loss_k)
            pen -= loss
            screen_lost += loss
    module_at = getattr(target, "module_at", None)
    side = None if module_at is None else module_at(x, y)
    if side is None:
        return ModuleHit(None, pen, 0.0, screen_lost)
    eff = effective_armor(target.track_thickness_mm, cos_impact)
    loss = min(pen, eff * stats.module_loss_k)
    return ModuleHit(side, pen - loss, damage * damage_fraction(pen, eff), screen_lost, loss)

def pen_after_modules(target, penetration, stats, x, y, cos_impact=1.0, dx=None, dy=None):
    """Только остаточное пробитие (для прицела и мозга ботов)."""
    return module_hit(target, penetration, 0.0, stats, cos_impact, x, y, dx, dy).pen

class Damageable:
    """Миксин для целей."""

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        raise NotImplementedError

    def frag_armor_bonus(self, normal=None):
        """Добавка к броне только для осколков (мм до учёта угла). Цели без экранов: 0."""
        return 0.0

    def frag_nominal_armor(self, normal=None):
        return None

    def frag_damage(self, penetration, damage, frag_frac, normal=None):
        """Урон осколков: damage * frag_frac, ослабленный номинальной бронёй грани (если она есть)."""
        base = damage * frag_frac
        armor = self.frag_nominal_armor(normal)
        if armor is None:
            return base
        return base * frag_armor_factor(armor, penetration)

    def take_hit(self, penetration, damage, cos_impact=1.0, normal=None, frag_frac=0.0):
        """Попадание снаряда. frag_frac > 0: у снаряда есть осколки (ФГ, HESH).
        Пробил хотя бы частично: урон пробития. Не пробил: урон осколков.
        Страховка: осколки при частичном пробитии не должны давать меньше, чем без пробития,
        поэтому берётся максимум из двух."""
        res = self.hit_result(penetration, cos_impact, normal)
        dealt = damage * res.damage_frac
        if frag_frac > 0.0 and not res.ricochet:
            dealt = max(dealt, self.frag_damage(penetration, damage, frag_frac, normal))
        self.hp = max(0.0, self.hp - dealt)
        return dealt

    def take_damage(self, amount):
        """Прямой урон без брони и рикошета (осколки, таран)."""
        self.hp = max(0.0, self.hp - amount)

    def incoming_k(self, kind):
        """Множитель входящего урона от взрывного снаряда kind (AmmoKind). Цели без сопротивления: 1.0."""
        return 1.0