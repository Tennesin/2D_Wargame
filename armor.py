"""armor.py — универсальные правила пробития. Одни и те же для стен, танков и любых будущих целей.
Объект сам знает только свою броню (в мм, уже умноженную на его коэффициент);
угол, рикошет и смягчённый урон считаются здесь."""
import math
from dataclasses import dataclass
from typing import Optional

# ==========================================
# 1. ПРАВИЛА
# ==========================================
RICOCHET_ANGLE = 70.0                                   # при угле к нормали больше этого — рикошет
RICOCHET_COS = math.cos(math.radians(RICOCHET_ANGLE))
PIERCE_SPREAD = 0.07                                    # окно ±7% вокруг пробития


# ==========================================
# 2. РЕЗУЛЬТАТ ПОПАДАНИЯ
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
# 3. ФОРМУЛЫ
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


# ==========================================
# 4. НАБОР ЦЕЛЕЙ ДЛЯ СНАРЯДОВ И ПРИЦЕЛА
# ==========================================
class TargetSet:
    """Объединяет источники целей (WallManager, танки...). У каждого источника должен быть
    raycast(x0, y0, x1, y1) -> (цель, t, normal) или None.
    У цели должны быть hit_result(...) и take_hit(...)."""

    def __init__(self, *sources):
        self.sources = list(sources)

    def add(self, source):
        self.sources.append(source)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Ближайшая цель на отрезке. ignore — источник, который пропускаем (стрелок, чтобы не попасть в себя)."""
        best = None
        for src in self.sources:
            if src is ignore:
                continue
            res = src.raycast(x0, y0, x1, y1)
            if res is not None and (best is None or res[1] < best[1]):
                best = res
        return best