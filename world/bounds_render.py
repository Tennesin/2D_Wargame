"""world/bounds_render.py — затемнение за краем мира: плавный переход в глухую темноту."""
import pygame

from engine import AlphaLayer, WORLD_HALF_PX

FADE_PX = 6000.0          # ширина плавного перехода за краем мира, px мира (60 м)
RINGS = 24                # из скольких колец-ступенек состоит градиент
DARK = (0, 0, 0)

class WorldBoundsRenderer:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, camera):
        view = screen.get_rect()
        x0, y0 = camera.world_to_screen(-WORLD_HALF_PX, -WORLD_HALF_PX)
        x1, y1 = camera.world_to_screen(WORLD_HALF_PX, WORLD_HALF_PX)
        world = pygame.Rect(round(x0), round(y0), round(x1 - x0), round(y1 - y0))
        if world.contains(view):
            return                                           # весь экран внутри мира: рисовать нечего

        fade = FADE_PX * camera.zoom
        pad = round(fade)
        outer = world.inflate(2 * pad, 2 * pad)              # дальше этой рамки темнота сплошная

        # 1. Глухая темнота: четыре прямоугольника вокруг внешней рамки (fill сам обрезает по экрану)
        solid = (
            (view.left, view.top, view.w, outer.top - view.top),                    # сверху
            (view.left, outer.bottom, view.w, view.bottom - outer.bottom),          # снизу
            (view.left, outer.top, outer.left - view.left, outer.h),                # слева
            (outer.right, outer.top, view.right - outer.right, outer.h),            # справа
        )
        for x, y, w, h in solid:
            if w > 0 and h > 0:
                screen.fill(DARK, (x, y, w, h))

        # 2. Градиент: кольца от края мира наружу, каждое темнее предыдущего
        if not outer.colliderect(view):
            return
        layer = self._alpha.begin(view.size)
        for i in range(RINGS):
            a = round(fade * i / RINGS)
            b = round(fade * (i + 1) / RINGS)
            if b <= a:
                continue
            alpha = int(255 * (i + 1) / RINGS)
            ring = world.inflate(2 * b, 2 * b)
            pygame.draw.rect(layer, (*DARK, alpha), ring, b - a)    # на SRCALPHA-слое рисунок заменяет пиксели
        screen.blit(layer, (0, 0))