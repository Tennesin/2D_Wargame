"""combat — правила пробития и тарана, снаряд, визуальные эффекты, линия прицела.
Снаружи: from combat import resolve_hit, resolve_ram, Damageable, TargetSet, EffectsSystem, compute_aim, ..."""
from .armor import (HitResult, Damageable, TargetSet,
                    resolve_hit, is_ricochet, effective_armor, damage_fraction)
from .ram import (RamResult, resolve_ram, can_push, ram_damage,
                  RESTITUTION_ROCK, RESTITUTION_TANK, MIN_CLOSING_MS)
from .projectile import Shell
from .effects import EffectsSystem
from .aim import AimInfo, AimRenderer, compute_aim

__all__ = ["HitResult", "Damageable", "TargetSet", "resolve_hit", "is_ricochet",
           "effective_armor", "damage_fraction", "RamResult", "resolve_ram", "can_push",
           "ram_damage", "RESTITUTION_ROCK", "RESTITUTION_TANK", "MIN_CLOSING_MS",
           "Shell", "EffectsSystem", "AimInfo", "AimRenderer", "compute_aim"]