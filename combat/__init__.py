"""combat — правила пробития и тарана, снаряд, визуальные эффекты, линия прицела.
Снаружи: from combat import resolve_hit, resolve_ram, Damageable, TargetSet, EffectsSystem, compute_aim, ..."""
from .armor import (
    HitResult, Damageable, RICOCHET_ANGLE, impact_cos, normalize_cos,
    pen_after_modules, resolve_hit, is_ricochet, effective_armor, damage_fraction,
    NORMALIZATION_MODULE_K, frag_armor_factor, FRAG_ARMOR_FULL_K, FRAG_ARMOR_ZERO_K,
    ModuleHit, module_hit
)
from .targets import TargetSet
from .ram import (
    RamResult, RamResult2D, resolve_ram, resolve_ram_2d, ram_restitution,
    can_push, ram_damage, RESTITUTION_ROCK, RESTITUTION_TANK, RESTITUTION_WALL,
    MIN_CLOSING_MS, RAM_FRICTION, RAM_SAFE_KJ, WALL_DMG_PER_KJ, STATIC_DYNAMIC_SHARE,
    TRACK_EDGE_K, TRACK_MID_K, ram_energy_kj, ram_damage_kj, press_velocity
)
from .projectile import Shell
from .splash import splash_damage, SPLASH_EDGE_K
from .artillery import blast_damage, armor_k
from .artillery_shell import ArtilleryShell
from .effects import EffectsSystem, Impact, Blast
from .aim import AimInfo, AimRenderer, compute_aim

__all__ = ["HitResult", "Damageable", "TargetSet", "resolve_hit", "is_ricochet", "impact_cos",
           "effective_armor", "damage_fraction", "RamResult", "resolve_ram", "can_push",
           "ram_damage", "RESTITUTION_ROCK", "RESTITUTION_TANK", "MIN_CLOSING_MS",
           "Shell", "EffectsSystem", "AimInfo", "AimRenderer", "compute_aim",
           "splash_damage", "SPLASH_EDGE_K", "Impact", "pen_after_modules", "RICOCHET_ANGLE",
           "blast_damage", "armor_k", "ArtilleryShell", "Blast", "normalize_cos",
           "NORMALIZATION_MODULE_K", "frag_armor_factor", "FRAG_ARMOR_FULL_K", "FRAG_ARMOR_ZERO_K",
           "ModuleHit", "module_hit", "RamResult2D", "resolve_ram_2d", "ram_restitution", "RAM_FRICTION",
           "RESTITUTION_WALL", "RAM_SAFE_KJ", "WALL_DMG_PER_KJ", "STATIC_DYNAMIC_SHARE",
           "TRACK_EDGE_K", "TRACK_MID_K", "ram_energy_kj", "ram_damage_kj", "press_velocity"]