"""combat — правила пробития и тарана, снаряд, визуальные эффекты, линия прицела.
Снаружи: from combat import resolve_hit, resolve_ram, Damageable, TargetSet, EffectsSystem, compute_aim, ..."""
from .armor import (HitResult, Damageable, TargetSet, RICOCHET_ANGLE, impact_cos,
                    resolve_hit, is_ricochet, effective_armor, damage_fraction)
from .ram import (RamResult, resolve_ram, can_push, ram_damage,
                  RESTITUTION_ROCK, RESTITUTION_TANK, MIN_CLOSING_MS)
from .projectile import Shell
from .splash import splash_damage, SPLASH_EDGE_K
from .effects import EffectsSystem, Impact
from .aim import AimInfo, AimRenderer, compute_aim

__all__ = ["HitResult", "Damageable", "TargetSet", "resolve_hit", "is_ricochet", "impact_cos",
           "effective_armor", "damage_fraction", "RamResult", "resolve_ram", "can_push",
           "ram_damage", "RESTITUTION_ROCK", "RESTITUTION_TANK", "MIN_CLOSING_MS",
           "Shell", "EffectsSystem", "AimInfo", "AimRenderer", "compute_aim",
           "splash_damage", "SPLASH_EDGE_K", "Impact"]