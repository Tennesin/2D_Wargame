"""engine — фундамент: масштаб, математика, геометрия, кэш, шум, графические помощники.
Снаружи: from engine import clamp, PX_PER_M и т.д.
Внутри пакета только относительные импорты."""
from .scale import PX_PER_M
from .palette import CONCRETE_SIDE, OUTLINE_DARK, SHADOW_ALPHA
from .param import Param
from .mathx import (normalize_angle, shortest_angle_diff, clamp, lerp, lerp_color,
                    heading_vector, find_free_fraction, fmt_num)
from .geometry import obb_hits_obb, obb_hits_convex, obb_segment_hit
from .cache import LRUCache
from .noise import hash_int, hash_float, value_noise
from .gfx import (FONT_SIZE_TITLE, FONT_SIZE_HEADER, FONT_SIZE_LABEL,
                  get_font, get_text, wrap_text, AlphaLayer)
from .commands import VehicleCommand, Shot

__all__ = [
    "PX_PER_M", "CONCRETE_SIDE", "OUTLINE_DARK", "SHADOW_ALPHA", "Param",
    "normalize_angle", "shortest_angle_diff", "clamp", "lerp", "lerp_color",
    "heading_vector", "find_free_fraction", "fmt_num",
    "obb_hits_obb", "obb_hits_convex", "obb_segment_hit", "LRUCache",
    "hash_int", "hash_float", "value_noise",
    "FONT_SIZE_TITLE", "FONT_SIZE_HEADER", "FONT_SIZE_LABEL",
    "get_font", "get_text", "wrap_text", "AlphaLayer",
    "VehicleCommand", "Shot",
]