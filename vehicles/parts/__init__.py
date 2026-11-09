"""parts — детали техники как данные: модель, реестр типов, библиотека рисования, авто-набор.
Снаружи: from vehicles.parts import Part, parts_for, draw_parts, PartCtx, SURFACE_HULL, BAND_*"""
from .model import (Part, PartCtx, SURFACES, SURFACE_HULL, SURFACE_TURRET, SURFACE_BARREL,
                    BAND_FENDER, BAND_DECK, BAND_COVER, BAND_TOP, BAND_ALL, CAT_DECOR, CAT_FUNCTIONAL)
from .registry import PART_TYPES, PartType, part_type, z_of
from . import library
from .defaults import default_parts, parts_for, barrel_parts
from .render import draw_parts

__all__ = ["Part", "PartCtx", "SURFACES", "SURFACE_HULL", "SURFACE_TURRET", "SURFACE_BARREL",
           "BAND_FENDER", "BAND_DECK", "BAND_COVER", "BAND_TOP", "BAND_ALL", "CAT_DECOR", "CAT_FUNCTIONAL",
           "PART_TYPES", "PartType", "part_type", "z_of", "default_parts", "parts_for", "barrel_parts",
           "draw_parts"]