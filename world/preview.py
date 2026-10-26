"""world/preview.py — маленькая картинка карты для «Новой игры»: из сида (без полной «запечки») и из MapData."""
import math

import pygame

from engine import PX_PER_M, WORLD_MIN_M, WORLD_MAX_M, clamp
from .natural import natural_shapes
from .terrain_render import MUD_FILL, SHALLOW_FILL, MID_FILL, DEEP_FILL, ROCK_TOP

PREVIEW_PX = 256                     # большая сторона картинки
GRASS = (102, 148, 74)
PALETTE = [GRASS, MUD_FILL, SHALLOW_FILL, MID_FILL, DEEP_FILL]     # индекс = уровень ландшафта
WALL_COLOR = (70, 70, 76)

def _size_m(v):
    return int(round(clamp(float(v), WORLD_MIN_M, WORLD_MAX_M)))

def _canvas(width_m, length_m):
    k = PREVIEW_PX / max(width_m, length_m)
    return max(1, round(width_m * k)), max(1, round(length_m * k))

def _transform(width_m, length_m):
    """(масштаб мировые px -> px превью, сдвиг x, сдвиг y)."""
    s = PREVIEW_PX / (max(width_m, length_m) * PX_PER_M)
    return s, width_m * PX_PER_M / 2.0, length_m * PX_PER_M / 2.0

def _poly(surf, color, pts, t):
    s, ox, oy = t
    pygame.draw.polygon(surf, color, [((x + ox) * s, (y + oy) * s) for x, y in pts])

def preview_from_seed(seed, width_m, length_m):
    """Превью случайной карты: озёра, грязь и камни прямо из генератора. Береговая линия
    отличается от запечённой карты не больше чем на клетку."""
    width_m, length_m = _size_m(width_m), _size_m(length_m)
    muds, lakes, rocks = natural_shapes(seed, width_m, length_m)
    surf = pygame.Surface(_canvas(width_m, length_m))
    surf.fill(GRASS)
    t = _transform(width_m, length_m)
    for pts in muds:                                      # вода выше грязи: рисуем грязь первой
        _poly(surf, MUD_FILL, pts, t)
    for shore, mid, deep in lakes:
        _poly(surf, SHALLOW_FILL, shore, t)
        _poly(surf, MID_FILL, mid, t)
        _poly(surf, DEEP_FILL, deep, t)
    for pts in rocks:
        _poly(surf, ROCK_TOP, pts, t)
    return surf

def preview_from_map(md):
    """Превью сохранённой карты: сетка ландшафта прореживается, поверх камни и стены."""
    land = md.landscape
    w, h = _canvas(md.width_m, md.length_m)
    xs = [min(land.cols - 1, int((i + 0.5) * land.cols / w)) for i in range(w)]
    data, cols = land.data, land.cols
    rows = []
    for j in range(h):
        jj = min(land.rows - 1, int((j + 0.5) * land.rows / h))
        row = data[jj * cols:(jj + 1) * cols]
        rows.append(bytes(row[x] for x in xs))
    img = pygame.image.frombuffer(b"".join(rows), (w, h), "P")
    img.set_palette(PALETTE)
    surf = img.convert()

    t = _transform(md.width_m, md.length_m)
    s, ox, oy = t
    for rock in md.rocks:
        _poly(surf, ROCK_TOP, rock.pts, t)
    for wl in md.walls:
        rad = math.radians(wl.angle)
        dx = -math.sin(rad) * wl.length_m * PX_PER_M / 2.0     # концы вдоль длины стены
        dy = math.cos(rad) * wl.length_m * PX_PER_M / 2.0
        a = ((wl.x - dx + ox) * s, (wl.y - dy + oy) * s)
        b = ((wl.x + dx + ox) * s, (wl.y + dy + oy) * s)
        pygame.draw.line(surf, WALL_COLOR, a, b, max(1, round(wl.width_m * PX_PER_M * s)))
    return surf