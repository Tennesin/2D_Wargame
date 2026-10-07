"""terrain_render.py — отрисовка естественных препятствий: вода, грязь, камни."""
import pygame

from terrain import ROCK, DEEP_WATER, SHALLOWS, MUD

MIN_SCREEN_R = 1.5           # пятна мельче этого радиуса (экранные px) не рисуем

SHALLOW_FILL = (124, 186, 198)
SHALLOW_FOAM = (206, 234, 238)
DEEP_FILL = (52, 116, 168)
DEEP_CORE = (40, 98, 150)
DEEP_EDGE = (34, 84, 130)

MUD_FILL = (108, 86, 58)
MUD_DARK = (88, 68, 46)
MUD_EDGE = (72, 56, 40)

ROCK_SHADOW = (40, 62, 40)
ROCK_SIDE = (92, 92, 96)
ROCK_TOP = (150, 150, 154)
ROCK_LIT = (178, 178, 182)
ROCK_FACET = (118, 118, 122)
ROCK_OUTLINE = (40, 40, 44)


def _shrink(pts, cx, cy, k, dx=0.0, dy=0.0):
    """Уменьшить фигуру относительно центра в k раз и сдвинуть."""
    return [(cx + (x - cx) * k + dx, cy + (y - cy) * k + dy) for x, y in pts]


class TerrainRenderer:
    def draw(self, screen, camera, terrain):
        w, h = screen.get_size()
        x0, y0 = camera.screen_to_world(0, 0)
        x1, y1 = camera.screen_to_world(w, h)
        z = camera.zoom

        for p in terrain.patches_in_rect(x0, y0, x1, y1):
            r = p.r_max * z
            if r < MIN_SCREEN_R:
                continue
            pts = [camera.world_to_screen(x, y) for x, y in p.pts]
            cx, cy = camera.world_to_screen(p.x, p.y)
            kind = p.kind
            if kind is SHALLOWS:
                pygame.draw.polygon(screen, SHALLOW_FILL, pts)
                pygame.draw.polygon(screen, SHALLOW_FOAM, pts, 2)
            elif kind is DEEP_WATER:
                pygame.draw.polygon(screen, DEEP_FILL, pts)
                pygame.draw.polygon(screen, DEEP_CORE, _shrink(pts, cx, cy, 0.6))
                pygame.draw.polygon(screen, DEEP_EDGE, pts, 1)
            elif kind is MUD:
                pygame.draw.polygon(screen, MUD_FILL, pts)
                pygame.draw.polygon(screen, MUD_DARK, _shrink(pts, cx, cy, 0.62))
                pygame.draw.polygon(screen, MUD_EDGE, pts, 1)
            elif kind is ROCK:
                self._draw_rock(screen, pts, cx, cy, r)

    @staticmethod
    def _draw_rock(screen, pts, cx, cy, r):
        if r >= 4:                                                    # тень (падает вправо-вниз)
            sx, sy = r * 0.10, r * 0.14
            pygame.draw.polygon(screen, ROCK_SHADOW, [(x + sx, y + sy) for x, y in pts])
        pygame.draw.polygon(screen, ROCK_SIDE, pts)                   # боковая грань

        off = -0.06 * r                                               # верхняя грань сдвинута к свету
        top = _shrink(pts, cx, cy, 0.82, off, off)
        pygame.draw.polygon(screen, ROCK_TOP, top)
        if r >= 10:                                                   # блик и грани
            lit = _shrink(pts, cx, cy, 0.45, off * 2.0, off * 2.0)
            pygame.draw.polygon(screen, ROCK_LIT, lit)
            for a, b in zip(top, lit):
                pygame.draw.line(screen, ROCK_FACET, a, b, 1)
        pygame.draw.polygon(screen, ROCK_OUTLINE, pts, 1)