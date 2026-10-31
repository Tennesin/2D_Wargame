"""game/hud/loot_pointers.py — жёлтые указатели у края экрана на останки улучшений, которых не видно в кадре."""
import math

from engine import get_text, FONT_SIZE_LABEL
from .pointers import edge_point, draw_triangle, avoid_interface

FILL = (240, 210, 70)
OUTLINE = (60, 48, 10)
TEXT = (255, 236, 150)
EDGE_INSET = 44
EDGE_SIZE = 13

class RemainsPointers:
    def __init__(self, loot, camera):
        self.loot = loot
        self.camera = camera

    def draw(self, screen):
        w, h = screen.get_size()
        for u in self.loot.remains:
            sx, sy = self.camera.world_to_screen(u.x, u.y)
            if 0 <= sx <= w and 0 <= sy <= h:
                continue                                       # останки в кадре: их видно в мире
            px, py, ang = edge_point(w, h, sx, sy, EDGE_INSET)
            nx, ny = avoid_interface(w, h, px, py, EDGE_SIZE, EDGE_INSET)
            if (nx, ny) != (px, py):
                px, py = nx, ny
                ang = math.atan2(sy - py, sx - px)             # остриё по-прежнему смотрит на останки
            draw_triangle(screen, px, py, ang, EDGE_SIZE, FILL, OUTLINE)

            label = get_text(f"{math.ceil(u.life)} с", FONT_SIZE_LABEL, TEXT)
            off = EDGE_SIZE + 16
            rect = label.get_rect(center=(round(px - math.cos(ang) * off), round(py - math.sin(ang) * off)))
            rect.clamp_ip(screen.get_rect())
            screen.blit(label, rect)