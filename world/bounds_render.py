"""world/bounds_render.py — граница мира: серые стены с угловыми башнями и затемнение всего, что за ними."""
import math

import pygame

from engine import AlphaLayer, WORLD, PX_PER_M, CONCRETE_SIDE, OUTLINE_DARK

FADE_PX = 6000.0          # на сколько px за краем мира рисуется земля (дальше сплошная темнота); читает ground_renderer
OUTSIDE_ALPHA = 150       # затемнение земли за стенами, 0..255
DARK = (0, 0, 0)

WALL_THICK_M = 6.0        # толщина стены, м
TOWER_M = 14.0            # сторона угловой башни, м (башня выступает наружу, внутрь карты не заходит)
JOINT_STEP_M = 10.0       # расстояние между швами плит стены, м
BEVEL_M = 0.6             # ширина боковой грани, м

WALL_TOP = (150, 150, 154)
WALL_JOINT = (126, 126, 130)
TOWER_TOP = (164, 164, 168)
TOWER_ROOF = (118, 118, 122)

class WorldBoundsRenderer:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, camera):
        view = screen.get_rect()
        x0, y0 = camera.world_to_screen(-WORLD.half_w_px, -WORLD.half_h_px)
        x1, y1 = camera.world_to_screen(WORLD.half_w_px, WORLD.half_h_px)
        world = pygame.Rect(round(x0), round(y0), round(x1 - x0), round(y1 - y0))
        if world.contains(view):
            return                                           # весь экран внутри мира: рисовать нечего
        z = camera.zoom
        self._draw_outside(screen, view, world, z)
        self._draw_walls(screen, view, world, z)

    # ---------- затемнение за краем ----------
    def _draw_outside(self, screen, view, world, z):
        pad = round(FADE_PX * z)
        outer = world.inflate(2 * pad, 2 * pad)              # дальше этой рамки земли нет: сплошная темнота

        solid = (
            (view.left, view.top, view.w, outer.top - view.top),                    # сверху
            (view.left, outer.bottom, view.w, view.bottom - outer.bottom),          # снизу
            (view.left, outer.top, outer.left - view.left, outer.h),                # слева
            (outer.right, outer.top, view.right - outer.right, outer.h),            # справа
        )
        for x, y, w, h in solid:
            if w > 0 and h > 0:
                screen.fill(DARK, (x, y, w, h))

        if not outer.colliderect(view):
            return
        layer = self._alpha.begin(view.size)
        layer.fill((*DARK, OUTSIDE_ALPHA))                   # всё затемняем...
        layer.fill((0, 0, 0, 0), world)                      # ...кроме мира (fill на SRCALPHA заменяет пиксели)
        screen.blit(layer, (0, 0))

    # ---------- стены и башни ----------
    def _draw_walls(self, screen, view, world, z):
        t = max(3, round(WALL_THICK_M * PX_PER_M * z))
        s = max(t + 2, round(TOWER_M * PX_PER_M * z))
        bevel = max(1, round(BEVEL_M * PX_PER_M * z))
        step = JOINT_STEP_M * PX_PER_M * z

        bands = (                                            # (прямоугольник, идёт ли вдоль оси X)
            (pygame.Rect(world.left, world.top - t, world.w, t), True),
            (pygame.Rect(world.left, world.bottom, world.w, t), True),
            (pygame.Rect(world.left - t, world.top, t, world.h), False),
            (pygame.Rect(world.right, world.top, t, world.h), False),
        )
        for rect, horizontal in bands:
            if not rect.colliderect(view):
                continue
            self._block(screen, rect, WALL_TOP, bevel)
            if step >= 8:
                self._joints(screen, view, rect, horizontal, step)

        towers = (                                           # квадрат целиком снаружи угла мира
            pygame.Rect(world.left - s, world.top - s, s, s),
            pygame.Rect(world.right, world.top - s, s, s),
            pygame.Rect(world.left - s, world.bottom, s, s),
            pygame.Rect(world.right, world.bottom, s, s),
        )
        for rect in towers:
            if rect.colliderect(view):
                self._block(screen, rect, TOWER_TOP, bevel * 2)
                roof = rect.inflate(-rect.w // 2, -rect.h // 2)
                pygame.draw.rect(screen, TOWER_ROOF, roof)
                pygame.draw.rect(screen, OUTLINE_DARK, roof, 1)

    @staticmethod
    def _block(screen, rect, top, bevel):
        """Бетонный блок: боковая грань, верхняя плоскость и контур."""
        pygame.draw.rect(screen, CONCRETE_SIDE, rect)
        pygame.draw.rect(screen, top, rect.inflate(-2 * bevel, -2 * bevel))
        pygame.draw.rect(screen, OUTLINE_DARK, rect, 1)

    @staticmethod
    def _joints(screen, view, rect, horizontal, step):
        """Швы между плитами стены; рисуем только те, что попадают на экран."""
        if horizontal:
            start, end, lo, hi = rect.left, rect.right, view.left, view.right
        else:
            start, end, lo, hi = rect.top, rect.bottom, view.top, view.bottom
        i = max(1, math.ceil((lo - start) / step))
        while start + i * step < min(end, hi):
            p = round(start + i * step)
            if horizontal:
                pygame.draw.line(screen, WALL_JOINT, (p, rect.top), (p, rect.bottom - 1))
            else:
                pygame.draw.line(screen, WALL_JOINT, (rect.left, p), (rect.right - 1, p))
            i += 1