"""combat — правила пробития, снаряд, визуальные эффекты, линия прицела.
Снаружи: from combat import resolve_hit, Damageable, TargetSet, EffectsSystem, compute_aim, ..."""
from .armor import (HitResult, Damageable, TargetSet,
                    resolve_hit, is_ricochet, effective_armor, damage_fraction)
from .projectile import Shell
from .effects import EffectsSystem
from .aim import AimInfo, AimRenderer, compute_aim

__all__ = ["HitResult", "Damageable", "TargetSet", "resolve_hit", "is_ricochet",
           "effective_armor", "damage_fraction", "Shell", "EffectsSystem",
           "AimInfo", "AimRenderer", "compute_aim"]