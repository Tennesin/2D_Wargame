"""game/hud/artillery_warning.py — предупреждение об ударе САУ: красная зона поражения, зона максимума
и четыре красных треугольника, которые сходятся к центру и исчезают вместе со снарядом.
Если зона целиком за экраном, у края рисуется красный указатель с секундами до падения."""
import math
import pygame

from engine import AlphaLayer, get_text, clamp, lerp, FONT_SIZE_LABEL
from .pointers import edge_point, draw_triangle

RED = (235, 55, 45)
RED_DARK = (70, 10, 10)
TEXT = (255, 170, 160)

OUTER_FILL_ALPHA = (40, 95)      # заливка внешней зоны: в начале полёта и перед падением
INNER_FILL_ALPHA = (50, 125)     # заливка зоны максимума
OUTER_LINE_ALPHA = 230
INNER_LINE_ALPHA = 190
OUTER_LINE_W = 3
INNER_LINE_W = 2

TRI_MIN, TRI_MAX, TRI_K = 9.0, 26.0, 0.09     # размер треугольника: доля радиуса зоны в пределах (мин, макс), px
EDGE_INSET = 40                                # отступ указателя от края экрана, px
EDGE_SIZE = 15

class ArtilleryWarning:
    def __init__(self, effects, camera):
        self.effects = effects
        self.camera = camera
        self._alpha = AlphaLayer()

    def draw(self, screen):
        shells = self.effects.artillery_shells
        if not shells:
            return
        w, h = screen.get_size()
        zoom = self.camera.zoom
        for shell in shells:
            sx, sy = self.camera.world_to_screen(*shell.target)
            r_out = shell.stats.outer_radius_px * zoom
            if sx + r_out < 0 or sx - r_out > w or sy + r_out < 0 or sy - r_out > h:
                self._draw_edge(screen, shell, sx, sy)           # зона за экраном: указатель у края
                continue
            u = shell.progress
            r_in = shell.stats.inner_radius_px * zoom
            self._draw_zone(screen, sx, sy, r_out, r_in, u)
            self._draw_triangles(screen, sx, sy, r_out, u)

    # ---------- зона поражения ----------
    def _draw_zone(self, screen, sx, sy, r_out, r_in, u):
        pad = OUTER_LINE_W + 2
        side = round(2.0 * r_out) + 2 * pad
        rect = pygame.Rect(round(sx - r_out) - pad, round(sy - r_out) - pad, side, side).clip(screen.get_rect())
        if rect.w <= 0 or rect.h <= 0:
            return
        layer = self._alpha.begin(rect.size)
        center = (round(sx) - rect.x, round(sy) - rect.y)
        ro, ri = max(1, int(round(r_out))), int(round(r_in))

        pygame.draw.circle(layer, (*RED, round(lerp(OUTER_FILL_ALPHA[0], OUTER_FILL_ALPHA[1], u))), center, ro)
        if ri >= 2:
            pygame.draw.circle(layer, (*RED, round(lerp(INNER_FILL_ALPHA[0], INNER_FILL_ALPHA[1], u))), center, ri)
            pygame.draw.circle(layer, (*RED, INNER_LINE_ALPHA), center, ri, min(INNER_LINE_W, ri))
        pygame.draw.circle(layer, (*RED, OUTER_LINE_ALPHA), center, ro, min(OUTER_LINE_W, ro))
        screen.blit(layer, rect.topleft)

    @staticmethod
    def _draw_triangles(screen, sx, sy, r_out, u):
        """Четыре треугольника стартуют на внешнем радиусе (сверху, снизу, слева, справа) остриём к центру
        и сходятся к нему пропорционально прогрессу полёта."""
        size = clamp(r_out * TRI_K, TRI_MIN, TRI_MAX)
        dist = r_out * (1.0 - u)                                  # расстояние острия от центра
        for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            ang = math.atan2(-oy, -ox)                            # остриё смотрит к центру
            ux, uy = math.cos(ang), math.sin(ang)
            tip_x, tip_y = sx + ox * dist, sy + oy * dist
            draw_triangle(screen, tip_x - ux * size, tip_y - uy * size, ang, size, RED, RED_DARK, width=2)

    # ---------- указатель у края ----------
    @staticmethod
    def _draw_edge(screen, shell, sx, sy):
        w, h = screen.get_size()
        px, py, ang = edge_point(w, h, sx, sy, EDGE_INSET)
        draw_triangle(screen, px, py, ang, EDGE_SIZE, RED, RED_DARK)
        label = get_text(f"{shell.time_left:.0f} с", FONT_SIZE_LABEL, TEXT)
        off = EDGE_SIZE + 16
        rect = label.get_rect(center=(round(px - math.cos(ang) * off), round(py - math.sin(ang) * off)))
        rect.clamp_ip(screen.get_rect())
        screen.blit(label, rect)