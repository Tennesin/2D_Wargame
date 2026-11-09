"""game/editor/part_icons.py — иконки типов деталей для палитры. Рисуются тем же кодом, что и в игре."""
import traceback

import pygame

from vehicles.look import Look
from vehicles.parts import PART_TYPES, PartCtx, new_part, local_bounds
from vehicles.parts.frame import PartPen
from vehicles.render.pen import Pen

ICON_PX = 40
SS = 3                         # суперсэмплинг: рисуем крупнее и сжимаем
ICON_TEAM = (64, 140, 200)

def make_part_icon(kind, size=ICON_PX):
    ptype = PART_TYPES[kind]
    surf = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    try:
        part = new_part(kind, ptype.surfaces[0], 0.0, 0.0)          # центр габарита в начале координат
        x0, y0, x1, y1 = local_bounds(part)
        extent = max(x1 - x0, y1 - y0, 0.12)
        k = min(60.0, (size - 6) / extent) * SS
        pen = Pen(surf, k)
        ptype.draw(PartPen(pen, part), part,
                   PartCtx(paint=None, look=Look(), layout=None, team=ICON_TEAM))
    except Exception:
        traceback.print_exc()
    return pygame.transform.smoothscale(surf, (size, size))

def make_part_icons():
    """{ключ типа: иконка}."""
    return {kind: make_part_icon(kind) for kind in PART_TYPES}