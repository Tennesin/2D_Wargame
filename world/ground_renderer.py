"""world/ground_renderer.py — отрисовка земли: чанки с зумом и декор."""
import math

import pygame

from engine import LRUCache
from .generator import CHUNK_SIZE, CELL_SIZE

MIN_CACHED_CHUNKS = 40

def ground_lod(zoom):
    """Чем дальше камера, тем крупнее клетка земли (меньше расчётов шума): 1, 2, 4, 8."""
    if zoom >= 0.35:
        return 1
    if zoom >= 0.17:
        return 2
    if zoom >= 0.12:
        return 4
    return 8

def _shade(color, k):
    """Умножить цвет на коэффициент (k<1 темнее, k>1 светлее)."""
    return tuple(max(0, min(255, int(c * k))) for c in color)

class GroundRenderer:
    def __init__(self, world_generator):
        self.world = world_generator
        self._chunk_cache = LRUCache()    # (cx, cy, lod) -> Surface, как построено (без масштаба)
        self._scaled_cache = LRUCache()   # (cx, cy) -> Surface, уже под текущий зум

    def set_zoom(self):
        """Зум сменился: масштабированные чанки устарели, базовые остаются."""
        self._scaled_cache.clear()

    def draw(self, screen, camera):
        z = camera.zoom
        lod = ground_lod(z)
        left, top = camera.origin_px()
        width, height = screen.get_size()

        span = CHUNK_SIZE * z                  # размер чанка на экране (дробный)
        size = math.ceil(span)                 # заготовка чуть больше шага -> швов между чанками нет

        cx0 = math.floor(left / span)
        cx1 = math.floor((left + width - 1) / span)
        cy0 = math.floor(top / span)
        cy1 = math.floor((top + height - 1) / span)

        visible = 0
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                tile = self._get_scaled_chunk(cx, cy, lod, size)
                screen.blit(tile, (round(cx * span) - left, round(cy * span) - top))
                visible += 1

        limit = max(MIN_CACHED_CHUNKS, visible + 12)
        self._chunk_cache.trim(limit)
        self._scaled_cache.trim(limit)

    # ==========================================
    # ЗЕМЛЯ И ЧАНКИ
    # ==========================================

    def _get_scaled_chunk(self, cx, cy, lod, size):
        key = (cx, cy)
        tile = self._scaled_cache.get(key)
        if tile is not None:
            self._chunk_cache.get((cx, cy, lod))  # освежаем базовый чанк, чтобы его не вытеснило
            return tile
        base = self._get_chunk(cx, cy, lod)
        tile = base if base.get_width() == size else pygame.transform.smoothscale(base, (size, size))
        self._scaled_cache.put(key, tile)
        return tile

    def _get_chunk(self, cx, cy, lod):
        return self._chunk_cache.get_or_build((cx, cy, lod), lambda: self._build_chunk(cx, cy, lod))

    def _build_chunk(self, cx, cy, lod):
        """Чанк в уменьшенном виде: при lod=4 это 8x8 клеток вместо 32x32 (в 16 раз меньше расчётов шума)."""
        cells = CHUNK_SIZE // (CELL_SIZE * lod)
        cell_world = CELL_SIZE * lod
        surf = pygame.Surface((cells * CELL_SIZE, cells * CELL_SIZE))
        for j in range(cells):
            for i in range(cells):
                color = self.world.ground_color(cx * cells + i, cy * cells + j, cell_world)
                surf.fill(color, (i * CELL_SIZE, j * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        if lod == 1:                         # на дальнем зуме декор всё равно меньше пикселя
            for deco in self.world.chunk_decorations(cx, cy):
                self._draw_decoration(surf, deco)
        return surf.convert()

    # ==========================================
    # ДЕКОР
    # ==========================================
    def _draw_decoration(self, surf, d):
        if d.kind == "flower":
            self._draw_flower(surf, d)
        elif d.kind == "stone":
            self._draw_stone(surf, d)
        elif d.kind == "bush":
            self._draw_bush(surf, d)
        elif d.kind == "tuft":
            self._draw_tuft(surf, d)

    @staticmethod
    def _draw_flower(surf, d):
        x, y = int(d.x), int(d.y)
        r = int(d.size)
        turn = (d.variant % 72)
        for k in range(5):
            a = math.radians(k * 72 + turn)
            px = int(round(x + math.cos(a) * r))
            py = int(round(y + math.sin(a) * r))
            pygame.draw.circle(surf, d.color, (px, py), max(2, int(r * 0.7)))
        pygame.draw.circle(surf, (250, 220, 60), (x, y), max(1, r // 2))

    @staticmethod
    def _draw_stone(surf, d):
        x, y = int(d.x), int(d.y)
        w = max(6, int(d.size * 2))
        h = max(5, int(d.size * 1.5) + d.variant % 3)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (x, y)
        pygame.draw.ellipse(surf, (45, 70, 45), rect.move(2, 3))          # тень
        pygame.draw.ellipse(surf, d.color, rect)
        pygame.draw.ellipse(surf, _shade(d.color, 0.7), rect, 1)          # контур
        hl = pygame.Rect(0, 0, max(2, w // 3), max(2, h // 3))
        hl.center = (x - w // 5, y - h // 5)
        pygame.draw.ellipse(surf, _shade(d.color, 1.25), hl)              # блик

    @staticmethod
    def _draw_bush(surf, d):
        x, y = int(d.x), int(d.y)
        r = max(4, int(d.size * 0.65))
        pygame.draw.circle(surf, _shade(d.color, 0.6), (x + 2, y + 3), r + 1)   # тень
        for ox, oy in ((-0.5, 0.3), (0.5, 0.2), (0.0, -0.5)):
            pygame.draw.circle(surf, d.color, (int(x + ox * r), int(y + oy * r)), r)
        pygame.draw.circle(surf, _shade(d.color, 1.3), (x - r // 3, y - r // 2), max(2, r // 2))
        if d.variant % 3 == 0:                                                  # ягоды
            for ox, oy in ((-3, -1), (2, 2), (3, -3)):
                pygame.draw.circle(surf, (200, 40, 50), (x + ox, y + oy), 2)

    @staticmethod
    def _draw_tuft(surf, d):
        x, y = int(d.x), int(d.y)
        s = d.size / 6.0
        flip = -1 if d.variant % 2 else 1
        for bx, by in ((-4, -6), (-1.5, -9), (1.5, -8), (4, -5)):
            pygame.draw.line(surf, d.color, (x, y),
                             (int(x + bx * s * flip), int(y + by * s)), 1)