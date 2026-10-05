"""wall/sprites.py — отрисовка стены: тень, бетонный блок, трещины, выделение, призрак."""
import math

import pygame

from common import PX_PER_M, clamp

WALL_SIDE = (92, 92, 96)
WALL_TOP = (158, 158, 162)
WALL_JOINT = (132, 132, 136)
WALL_OUTLINE = (40, 40, 44)
CRACK_COLOR = (36, 34, 32)
SELECT_COLOR = (255, 220, 80)

GHOST_OK_FILL = (205, 210, 220, 110)
GHOST_OK_BORDER = (255, 255, 255, 200)
GHOST_BAD_FILL = (230, 40, 40, 140)
GHOST_BAD_BORDER = (255, 90, 90, 230)

SHADOW_ALPHA = 80
SHADOW_OFFSET_M = (0.30, 0.40)
JOINT_STEP_M = 2.0            # расстояние между швами плит
BEVEL_M = 0.12                # ширина «боковой грани»
CRACK_GROW = 0.12             # на сколько «урона» трещина вырастает от начала до полной длины
CRACK_WIDTH_M = 0.05


class WallRenderer:
    @staticmethod
    def _screen_rect(camera, wall):
        left, top, right, bottom = wall.rect()
        x0, y0 = camera.world_to_screen(left, top)
        x1, y1 = camera.world_to_screen(right, bottom)
        x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
        return pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    # ---------- все стены ----------
    def draw_all(self, screen, camera, walls):
        view = screen.get_rect()
        ppm = PX_PER_M * camera.zoom
        visible = []
        for wall in walls.items:
            rect = self._screen_rect(camera, wall)
            if rect.inflate(60, 60).colliderect(view):
                visible.append((wall, rect))

        for _, rect in visible:                       # сначала все тени, чтобы не ложились поверх соседей
            self._draw_shadow(screen, rect, ppm)
        for wall, rect in visible:
            self._draw_body(screen, wall, rect, ppm)
            self._draw_cracks(screen, camera, wall, rect, ppm)
            if wall is walls.selected:
                pygame.draw.rect(screen, SELECT_COLOR, rect.inflate(6, 6), 2)

    @staticmethod
    def _draw_shadow(screen, rect, ppm):
        ox, oy = (round(v * ppm) for v in SHADOW_OFFSET_M)
        area = rect.move(ox, oy).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        layer.fill((0, 0, 0, SHADOW_ALPHA))
        screen.blit(layer, area.topleft)

    @staticmethod
    def _draw_body(screen, wall, rect, ppm):
        pygame.draw.rect(screen, WALL_SIDE, rect)
        bevel = max(0, min(round(BEVEL_M * ppm), (min(rect.w, rect.h) - 1) // 2))
        top = rect.inflate(-2 * bevel, -2 * bevel)
        if top.w > 0 and top.h > 0:
            pygame.draw.rect(screen, WALL_TOP, top)

            # швы между плитами вдоль длинной стороны
            long_is_y = wall.length_m >= wall.width_m
            span = wall.length_m if long_is_y else wall.width_m
            step_px = JOINT_STEP_M * ppm
            if step_px >= 8:
                i = 1
                while i * JOINT_STEP_M < span - 0.05:
                    off = round(i * step_px)
                    if long_is_y:
                        y = rect.y + off
                        pygame.draw.line(screen, WALL_JOINT, (top.x, y), (top.right - 1, y))
                    else:
                        x = rect.x + off
                        pygame.draw.line(screen, WALL_JOINT, (x, top.y), (x, top.bottom - 1))
                    i += 1
        pygame.draw.rect(screen, WALL_OUTLINE, rect, 1)

    @staticmethod
    def _draw_cracks(screen, camera, wall, rect, ppm):
        d = wall.damage_fraction
        if d <= 0.0:
            return
        width = max(1, round(CRACK_WIDTH_M * ppm))
        old_clip = screen.get_clip()
        screen.set_clip(rect.clip(old_clip))
        for threshold, pts in wall.cracks():
            if d < threshold:                          # пороги отсортированы — дальше трещин ещё нет
                break
            grow = clamp((d - threshold) / CRACK_GROW, 0.0, 1.0)
            n = max(1, math.ceil(grow * (len(pts) - 1)))
            line = [camera.world_to_screen(wall.x + ox, wall.y + oy) for ox, oy in pts[:n + 1]]
            pygame.draw.lines(screen, CRACK_COLOR, False, line, width)
        screen.set_clip(old_clip)

    # ---------- призрак при выборе места ----------
    def draw_preview(self, screen, camera, wall, blocked):
        rect = self._screen_rect(camera, wall)
        area = rect.clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        fill, border = (GHOST_BAD_FILL, GHOST_BAD_BORDER) if blocked else (GHOST_OK_FILL, GHOST_OK_BORDER)
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        layer.fill(fill)
        pygame.draw.rect(layer, border, layer.get_rect(), 2)
        screen.blit(layer, area.topleft)