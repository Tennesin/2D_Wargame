"""wall/sprites.py — отрисовка стены: тень, бетонный блок, трещины, выделение, ручка поворота, призрак."""
import math

import pygame

from common import PX_PER_M, clamp
from .params import ROTATE_HANDLE_RADIUS_PX

WALL_SIDE = (92, 92, 96)
WALL_TOP = (158, 158, 162)
WALL_JOINT = (132, 132, 136)
WALL_OUTLINE = (40, 40, 44)
CRACK_COLOR = (36, 34, 32)
SELECT_COLOR = (255, 220, 80)
HANDLE_COLOR = (255, 255, 255)

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
    # ---------- помощники ----------
    @staticmethod
    def _to_screen(camera, wall, u, v):
        """Локальная точка стены (px мира от центра) -> экранные координаты."""
        wx, wy = wall.to_world(u, v)
        return camera.world_to_screen(wx, wy)

    def _quad(self, camera, wall, pad=0.0):
        """Четыре угла стены на экране; pad (px мира) раздувает прямоугольник наружу."""
        hw, hl = wall.half_w_px + pad, wall.half_l_px + pad
        return [self._to_screen(camera, wall, u, v)
                for u, v in ((-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl))]

    @staticmethod
    def _bounds(points):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x0, y0 = math.floor(min(xs)), math.floor(min(ys))
        return pygame.Rect(x0, y0, math.ceil(max(xs)) - x0 + 1, math.ceil(max(ys)) - y0 + 1)

    # ---------- все стены ----------
    def draw_all(self, screen, camera, walls):
        view = screen.get_rect()
        ppm = PX_PER_M * camera.zoom
        visible = []
        for wall in walls.items:
            quad = self._quad(camera, wall)
            if self._bounds(quad).inflate(60, 60).colliderect(view):
                visible.append((wall, quad))

        for _, quad in visible:                       # сначала все тени, чтобы не ложились поверх соседей
            self._draw_shadow(screen, quad, ppm)
        for wall, quad in visible:
            self._draw_body(screen, camera, wall, quad, ppm)
            self._draw_cracks(screen, camera, wall)
            if wall is walls.selected:
                self._draw_selection(screen, camera, wall)

    def _draw_shadow(self, screen, quad, ppm):
        ox, oy = (v * ppm for v in SHADOW_OFFSET_M)
        pts = [(x + ox, y + oy) for x, y in quad]
        area = self._bounds(pts).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        pygame.draw.polygon(layer, (0, 0, 0, SHADOW_ALPHA),
                            [(x - area.x, y - area.y) for x, y in pts])
        screen.blit(layer, area.topleft)

    def _draw_body(self, screen, camera, wall, quad, ppm):
        hw, hl = wall.half_w_px, wall.half_l_px
        pygame.draw.polygon(screen, WALL_SIDE, quad)

        bevel = min(BEVEL_M * PX_PER_M, min(hw, hl) * 0.6)
        tw, tl = hw - bevel, hl - bevel                # верхняя плоскость блока
        top = [self._to_screen(camera, wall, u, v)
               for u, v in ((-tw, -tl), (tw, -tl), (tw, tl), (-tw, tl))]
        pygame.draw.polygon(screen, WALL_TOP, top)

        # швы между плитами вдоль длинной стороны
        if JOINT_STEP_M * ppm >= 8:
            long_is_y = wall.length_m >= wall.width_m
            span = wall.length_m if long_is_y else wall.width_m
            i = 1
            while i * JOINT_STEP_M < span - 0.05:
                off = i * JOINT_STEP_M * PX_PER_M
                if long_is_y:
                    a, b = (-tw, -hl + off), (tw, -hl + off)
                else:
                    a, b = (-hw + off, -tl), (-hw + off, tl)
                pygame.draw.line(screen, WALL_JOINT,
                                 self._to_screen(camera, wall, *a),
                                 self._to_screen(camera, wall, *b))
                i += 1
        pygame.draw.polygon(screen, WALL_OUTLINE, quad, 1)

    def _draw_cracks(self, screen, camera, wall):
        d = wall.damage_fraction
        if d <= 0.0:
            return
        width = max(1, round(CRACK_WIDTH_M * PX_PER_M * camera.zoom))
        for threshold, pts in wall.cracks():
            if d < threshold:                          # пороги отсортированы — дальше трещин ещё нет
                break
            grow = clamp((d - threshold) / CRACK_GROW, 0.0, 1.0)
            n = max(1, math.ceil(grow * (len(pts) - 1)))
            line = [self._to_screen(camera, wall, u, v) for u, v in pts[:n + 1]]
            pygame.draw.lines(screen, CRACK_COLOR, False, line, width)

    def _draw_selection(self, screen, camera, wall):
        frame = self._quad(camera, wall, pad=3.0 / camera.zoom)     # рамка на 3 экранных px шире стены
        pygame.draw.polygon(screen, SELECT_COLOR, frame, 2)

        cx, cy = camera.world_to_screen(wall.x, wall.y)             # белая точка поворота в центре
        center = (round(cx), round(cy))
        pygame.draw.circle(screen, HANDLE_COLOR, center, ROTATE_HANDLE_RADIUS_PX)
        pygame.draw.circle(screen, WALL_OUTLINE, center, ROTATE_HANDLE_RADIUS_PX, 1)

    # ---------- призрак при выборе места ----------
    def draw_preview(self, screen, camera, wall, blocked):
        quad = self._quad(camera, wall)
        area = self._bounds(quad).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        fill, border = (GHOST_BAD_FILL, GHOST_BAD_BORDER) if blocked else (GHOST_OK_FILL, GHOST_OK_BORDER)
        pts = [(x - area.x, y - area.y) for x, y in quad]
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        pygame.draw.polygon(layer, fill, pts)
        pygame.draw.polygon(layer, border, pts, 2)
        screen.blit(layer, area.topleft)