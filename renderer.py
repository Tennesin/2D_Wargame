"""renderer.py — вся отрисовка: земля (чанки с зумом), декор, танк, отладка."""
import math
from collections import OrderedDict

import pygame

from common import PX_PER_M
from core import CHUNK_SIZE, CELL_SIZE
from tank import TankRenderer

# ---------- Земля ----------
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


def _egg(a, front, rear, n=28):
    """Яйцевидный контур башни: узкий нос, широкая корма. a — полуширина, front/rear — полудлины (м)."""
    pts = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        ux, uy = math.sin(t), math.cos(t)                      # uy > 0 — вперёд
        x = a * ux * (1.0 - 0.22 * max(0.0, uy) ** 2)
        y = -(front if uy > 0 else rear) * uy
        pts.append((x, y))
    return pts


class _Pen:
    """Рисует в метрах относительно центра поверхности (с суперсэмплингом и контуром 1 px)."""

    def __init__(self, surf, k, ox=0.0, oy=0.0):
        self.s = surf
        self.k = k                        # пикселей поверхности на метр
        self.ox, self.oy = ox, oy         # сдвиг начала координат, м
        self.cx = surf.get_width() / 2
        self.cy = surf.get_height() / 2

    def p(self, x, y):
        return (self.cx + (x + self.ox) * self.k, self.cy + (y + self.oy) * self.k)

    def poly(self, color, pts, outline=OUTLINE):
        big = [self.p(x, y) for x, y in pts]
        pygame.draw.polygon(self.s, color, big)
        if outline:
            pygame.draw.polygon(self.s, outline, big, OUTLINE_W)

    def rect(self, color, x, y, w, h, outline=OUTLINE, r=0.0):
        x0, y0 = self.p(x, y)
        rect = pygame.Rect(round(x0), round(y0), max(1, round(w * self.k)), max(1, round(h * self.k)))
        radius = round(r * self.k)
        pygame.draw.rect(self.s, color, rect, border_radius=radius)
        if outline:
            pygame.draw.rect(self.s, outline, rect, OUTLINE_W, border_radius=radius)

    def ellipse(self, color, cx, cy, rx, ry, outline=OUTLINE):
        x0, y0 = self.p(cx - rx, cy - ry)
        rect = pygame.Rect(round(x0), round(y0), max(2, round(2 * rx * self.k)), max(2, round(2 * ry * self.k)))
        pygame.draw.ellipse(self.s, color, rect)
        if outline:
            pygame.draw.ellipse(self.s, outline, rect, OUTLINE_W)

    def line(self, color, x1, y1, x2, y2, w):
        pygame.draw.line(self.s, color, self.p(x1, y1), self.p(x2, y2), max(1, round(w * self.k)))

    def set_clip(self, x, y, w, h):
        x0, y0 = self.p(x, y)
        self.s.set_clip(pygame.Rect(round(x0), round(y0), round(w * self.k), round(h * self.k)))

    def clear_clip(self):
        self.s.set_clip(None)


class Renderer:
    def __init__(self, world_generator):
        self.world = world_generator
        self.font = pygame.font.Font(None, 22)

        self._zoom = None                   # зум, под который сейчас построены кэши
        self._ppm = 0.0                     # пикселей экрана на метр эталонного спрайта (= PX_PER_M * zoom)

        self._chunk_cache = OrderedDict()   # (cx, cy, lod) -> Surface, как построено (без масштаба)
        self._scaled_cache = OrderedDict()  # (cx, cy) -> Surface, уже под текущий зум

        self.tank_renderer = TankRenderer()

    # ==========================================
    # ГЛАВНЫЙ МЕТОД
    # ==========================================
    def draw(self, screen, camera, tank, debug_lines=None, effects=None):
        self._sync_zoom(camera.zoom)
        self._draw_ground(screen, camera)
        if effects is not None:
            effects.draw_ground(screen, camera)      # пятна от взрывов лежат под танком
        self.tank_renderer.draw(screen, camera, tank)
        if effects is not None:
            effects.draw(screen, camera)
        if debug_lines:
            self._draw_debug(screen, debug_lines)

    def _sync_zoom(self, zoom):
        """При смене зума сбрасываем всё, что зависит от масштаба (земля-базовые чанки остаются)."""
        if zoom == self._zoom:
            return
        self._zoom = zoom
        self._ppm = PX_PER_M * zoom
        self._scaled_cache.clear()
        self.tank_renderer.set_zoom(self._ppm)

    # ==========================================
    # ЗЕМЛЯ И ЧАНКИ
    # ==========================================
    def _draw_ground(self, screen, camera):
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
        self._trim_ordered(self._chunk_cache, limit)
        self._trim_ordered(self._scaled_cache, limit)

    @staticmethod
    def _trim_ordered(cache, limit):
        while len(cache) > limit:
            cache.popitem(last=False)

    def _get_scaled_chunk(self, cx, cy, lod, size):
        key = (cx, cy)
        tile = self._scaled_cache.get(key)
        if tile is None:
            base = self._get_chunk(cx, cy, lod)
            tile = base if base.get_width() == size else pygame.transform.smoothscale(base, (size, size))
            self._scaled_cache[key] = tile
        else:
            self._scaled_cache.move_to_end(key)
            bkey = (cx, cy, lod)
            if bkey in self._chunk_cache:
                self._chunk_cache.move_to_end(bkey)
        return tile

    def _get_chunk(self, cx, cy, lod):
        key = (cx, cy, lod)
        chunk = self._chunk_cache.get(key)
        if chunk is None:
            chunk = self._build_chunk(cx, cy, lod)
            self._chunk_cache[key] = chunk
        else:
            self._chunk_cache.move_to_end(key)
        return chunk

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

    # ==========================================
    # ОТЛАДКА
    # ==========================================
    def _draw_debug(self, screen, lines):
        y = 8
        for text in lines:
            shadow = self.font.render(text, True, (0, 0, 0))
            label = self.font.render(text, True, (255, 255, 255))
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += 20