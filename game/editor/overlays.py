"""game/editor/overlays.py — подсказки редактора поверх мира: призрак и рамка камня, круг кисти."""
import math
import pygame

from engine import AlphaLayer

GHOST_OK_FILL = (205, 210, 220, 110)
GHOST_OK_BORDER = (255, 255, 255, 200)
GHOST_BAD_FILL = (230, 40, 40, 140)
GHOST_BAD_BORDER = (255, 90, 90, 230)
SELECT_COLOR = (255, 220, 80)
BRUSH_COLORS = {"plain": (190, 230, 120), "mud": (170, 130, 90),
                "water": (110, 190, 230), "deep": (60, 110, 190)}

class RockOverlay:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, camera, tool):
        if tool.selected is not None:
            pts = [camera.world_to_screen(x, y) for x, y in tool.selected.pts]
            pygame.draw.polygon(screen, SELECT_COLOR, pts, 2)
        preview = tool.preview()
        if preview is not None:
            self._ghost(screen, camera, *preview)

    def _ghost(self, screen, camera, patch, blocked):
        pts = [camera.world_to_screen(x, y) for x, y in patch.pts]
        x0 = math.floor(min(p[0] for p in pts))
        y0 = math.floor(min(p[1] for p in pts))
        x1 = math.ceil(max(p[0] for p in pts))
        y1 = math.ceil(max(p[1] for p in pts))
        area = pygame.Rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        fill, border = (GHOST_BAD_FILL, GHOST_BAD_BORDER) if blocked else (GHOST_OK_FILL, GHOST_OK_BORDER)
        local = [(x - area.x, y - area.y) for x, y in pts]
        layer = self._alpha.begin(area.size)
        pygame.draw.polygon(layer, fill, local)
        pygame.draw.polygon(layer, border, local, 2)
        screen.blit(layer, area.topleft)

class BrushOverlay:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, camera, tool):
        cur = tool.cursor()
        if cur is None:
            return
        x, y, r_px, key = cur
        sx, sy = camera.world_to_screen(x, y)
        r = max(2, round(r_px * camera.zoom))
        side = 2 * r + 6
        area = pygame.Rect(round(sx) - r - 3, round(sy) - r - 3, side, side).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        color = BRUSH_COLORS[key]
        center = (round(sx) - area.x, round(sy) - area.y)
        layer = self._alpha.begin(area.size)
        pygame.draw.circle(layer, (*color, 50), center, r)
        pygame.draw.circle(layer, (*color, 230), center, r, 2)
        screen.blit(layer, area.topleft)