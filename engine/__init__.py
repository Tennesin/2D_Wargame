"""engine — фундамент: масштаб, математика, геометрия, кэш, шум, графические помощники.
Снаружи: from engine import clamp, PX_PER_M и т.д.
Внутри пакета только относительные импорты."""
from .scale import PX_PER_M, WORLD, WORLD_MIN_M, WORLD_MAX_M, WORLD_DEFAULT_M
from .palette import (CONCRETE_SIDE, OUTLINE_DARK, SHADOW_ALPHA, AMMO_COLORS,
                      COLOR_GOOD, COLOR_WARN, COLOR_BAD, hp_color)
from .param import Param
from .mathx import (TAU, normalize_angle, shortest_angle_diff, clamp, lerp, lerp_color, shade_color,
                    heading_vector, find_free_fraction, fmt_num, bearing_deg, round_to)
from .kinds import Team, VehicleKind, TargetType, AmmoKind
from .geometry import (obb_hits_obb, obb_hits_convex, obb_segment_hit, obb_outside_rect,
                       obb_contact, obb_convex_contact, obb_distance_to_point, shrink_polygon,
                       convex_segment_hit, point_in_convex, is_convex, edge_normal_away,
                       to_local_frame, vec_to_local, vec_from_local)
from .cache import LRUCache
from .noise import hash_int, hash_float, value_noise, SEED_SALT
from .gfx import (FONT_SIZE_TITLE, FONT_SIZE_HEADER, FONT_SIZE_LABEL,
                  get_font, get_text, wrap_text, AlphaLayer, blur_surface)
from .commands import VehicleCommand, Shot, AmmoStats, ArtilleryStats

__all__ = [
    "PX_PER_M", "WORLD", "WORLD_MIN_M", "WORLD_MAX_M", "WORLD_DEFAULT_M",
    "CONCRETE_SIDE", "OUTLINE_DARK", "SHADOW_ALPHA", "AMMO_COLORS",
    "COLOR_GOOD", "COLOR_WARN", "COLOR_BAD", "hp_color", "Param",
    "TAU", "normalize_angle", "shortest_angle_diff", "clamp", "lerp", "lerp_color", "shade_color",
    "heading_vector", "find_free_fraction", "fmt_num", "bearing_deg", "round_to",
    "Team", "VehicleKind", "TargetType", "AmmoKind",
    "obb_hits_obb", "obb_hits_convex", "obb_segment_hit", "obb_outside_rect",
    "obb_contact", "convex_segment_hit", "point_in_convex", "is_convex", "edge_normal_away",
    "to_local_frame", "vec_to_local", "vec_from_local",
    "obb_convex_contact", "obb_distance_to_point", "shrink_polygon",
    "LRUCache", "hash_int", "hash_float", "value_noise", "SEED_SALT",
    "FONT_SIZE_TITLE", "FONT_SIZE_HEADER", "FONT_SIZE_LABEL",
    "get_font", "get_text", "wrap_text", "AlphaLayer", "blur_surface",
    "VehicleCommand", "Shot", "AmmoStats", "ArtilleryStats",
]