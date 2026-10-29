"""world/terrain_render.py — отрисовка естественных препятствий: вода и грязь (из сетки ландшафта), камни."""
import math
import time

import pygame

from engine import CONCRETE_SIDE, OUTLINE_DARK, LRUCache, PX_PER_M, shrink_polygon
from .landscape import BLOCK_CELLS, L_MUD, L_SHALLOWS, L_WATER, L_DEEP
from .terrain import ROCK

MIN_SCREEN_R = 1.5           # камни мельче этого радиуса (экранные px) не рисуем

SHALLOW_FILL = (124, 186, 198)
SHALLOW_FOAM = (206, 234, 238)
MID_FILL = (78, 152, 190)
MID_EDGE = (96, 168, 204)
DEEP_FILL = (44, 106, 158)
DEEP_EDGE = (34, 84, 130)

MUD_FILL = (108, 86, 58)
MUD_EDGE = (72, 56, 40)

ROCK_SHADOW = (40, 62, 40)
ROCK_SIDE = CONCRETE_SIDE
ROCK_OUTLINE = OUTLINE_DARK
ROCK_TOP = (150, 150, 154)
ROCK_LIT = (178, 178, 182)
ROCK_FACET = (118, 118, 122)

# --- блоки воды ---
K = 6                        # пикселей текстуры на клетку
PAD = 1                      # клетки соседей по краю блока (для плавного контура)
FILL_LEVEL = 128             # порог заливки (0..255 после растяжения маски)
EDGE_LEVEL = 84              # порог кромки: ниже заливки, поэтому вокруг неё остаётся рамка
BUILD_MS = 8.0               # сколько мс за кадр можно тратить на сборку блоков
BLOCK_CACHE = 500
SCALED_CACHE = 200
WATER_PRELOAD_MAX = 600      # сколько текстур воды (≈150 КБ каждая) предзагружать впрок за пределами экрана
PALETTE = [(0, 0, 0), (255, 255, 255)]

def _table(test):
    """Таблица для bytes.translate: уровень клетки -> 1, если клетка входит в слой."""
    return bytes(1 if test(v) else 0 for v in range(256))

LAYERS = (    # снизу вверх: (таблица, заливка, кромка)
    (_table(lambda v: v == L_MUD), MUD_FILL, MUD_EDGE),
    (_table(lambda v: v >= L_SHALLOWS), SHALLOW_FILL, SHALLOW_FOAM),
    (_table(lambda v: v >= L_WATER), MID_FILL, MID_EDGE),
    (_table(lambda v: v >= L_DEEP), DEEP_FILL, DEEP_EDGE),
)

def _window(grid, bx, by):
    """Уровни клеток блока плюс PAD клеток вокруг, одной строкой байт. За краем карты берётся
    ближайшая клетка (вода у границы не обрывается рамкой)."""
    n = BLOCK_CELLS + 2 * PAD
    i0 = bx * BLOCK_CELLS - PAD
    j0 = by * BLOCK_CELLS - PAD
    a, b = max(i0, 0), min(i0 + n, grid.cols)
    rows = []
    for j in range(j0, j0 + n):
        jj = min(max(j, 0), grid.rows - 1)
        seg = bytes(grid.data[jj * grid.cols + a: jj * grid.cols + b])
        rows.append(seg[:1] * (a - i0) + seg + seg[-1:] * (i0 + n - b))
    return b"".join(rows), n

class TerrainRenderer:
    def __init__(self, wide=False):
        self.wide = wide
        self._blocks = LRUCache(BLOCK_CACHE)
        self._scaled = LRUCache(SCALED_CACHE)
        self._zoom = None

    # ==========================================
    # ВОДА И ГРЯЗЬ
    # ==========================================
    @staticmethod
    def _visible_blocks(camera, size, grid):
        w, h = size
        x0, y0 = camera.screen_to_world(0, 0)
        x1, y1 = camera.screen_to_world(w, h)
        i0, i1, j0, j1 = grid.cell_range(x0, y0, x1, y1)
        if i1 < i0 or j1 < j0:
            return []
        return [(bx, by) for by in range(j0 // BLOCK_CELLS, j1 // BLOCK_CELLS + 1)
                for bx in range(i0 // BLOCK_CELLS, i1 // BLOCK_CELLS + 1)]

    def _build_block(self, grid, bx, by):
        """Текстура блока (BLOCK_CELLS*K px, с прозрачностью) или None, если в блоке только трава."""
        window, n = _window(grid, bx, by)
        if window.count(0) == len(window):
            return None
        side = BLOCK_CELLS * K
        out = pygame.Surface((side, side), pygame.SRCALPHA)
        out.fill((*SHALLOW_FOAM, 0))             # цвет «прозрачных» пикселей: без тёмной каймы при растяжении
        drawn = False
        for table, fill, edge in LAYERS:
            bits = window.translate(table)
            if 1 not in bits:
                continue
            small = pygame.image.frombuffer(bits, (n, n), "P")
            small.set_palette(PALETTE)
            big = pygame.transform.smoothscale(small.convert(), (n * K, n * K))
            for level, color in ((EDGE_LEVEL, edge), (FILL_LEVEL, fill)):
                mask = pygame.mask.from_threshold(big, (255, 255, 255, 255), (255 - level,) * 3 + (255,))
                layer = mask.to_surface(setcolor=(*color, 255), unsetcolor=(*color, 0))
                out.blit(layer, (-PAD * K, -PAD * K))
            drawn = True
        if not drawn:
            return None
        valid_w = min(BLOCK_CELLS, grid.cols - bx * BLOCK_CELLS) * K     # последний блок может быть неполным
        valid_h = min(BLOCK_CELLS, grid.rows - by * BLOCK_CELLS) * K
        if valid_w < side:
            out.fill((*SHALLOW_FOAM, 0), (valid_w, 0, side - valid_w, side))
        if valid_h < side:
            out.fill((*SHALLOW_FOAM, 0), (0, valid_h, side, side - valid_h))
        return out

    def _block_texture(self, grid, bx, by):
        """Текстура блока из кэша или свежесобранная."""
        key = (bx, by)
        ver = grid.block_version(bx, by)
        entry = self._blocks.get(key)
        if entry is not None and entry[0] == ver:
            return entry[1]
        tex = self._build_block(grid, bx, by)
        self._blocks.put(key, (ver, tex))
        self._scaled.discard(key)
        return tex

    def preload_iter(self, camera, size, terrain):
        """Строит блоки воды по одному, отдавая долю готовности 0..1."""
        grid = terrain.grid
        visible = self._visible_blocks(camera, size, grid)
        blocks = visible
        if self.wide:
            nx = -(-grid.cols // BLOCK_CELLS)
            ny = -(-grid.rows // BLOCK_CELLS)
            self._blocks.limit = max(BLOCK_CACHE, nx * ny)    # в кэше должны поместиться все блоки карты
            seen = set(visible)
            block_px = BLOCK_CELLS * PX_PER_M
            cbx = (camera.x + grid.half_w_px) / block_px - 0.5
            cby = (camera.y + grid.half_h_px) / block_px - 0.5
            rest = [(bx, by) for by in range(ny) for bx in range(nx) if (bx, by) not in seen]
            rest.sort(key=lambda b: (b[0] - cbx) ** 2 + (b[1] - cby) ** 2)
            blocks = visible + rest
        total = max(1, len(blocks))
        textures = 0
        for n, (bx, by) in enumerate(blocks, 1):
            tex = self._block_texture(grid, bx, by)
            if self.wide and n > len(visible) and tex is not None:
                textures += 1
                if textures >= WATER_PRELOAD_MAX:              # запас памяти: дальше достроится в бою
                    break
            yield n / total
        yield 1.0

    def preload(self, camera, size, terrain):
        """Синхронно строит все видимые блоки."""
        for _ in self.preload_iter(camera, size, terrain):
            pass

    def _draw_water(self, screen, camera, grid):
        z = camera.zoom
        if z != self._zoom:                      # зум сменился: масштабированные блоки устарели
            self._zoom = z
            self._scaled.clear()
        span = BLOCK_CELLS * PX_PER_M * z
        size = max(1, math.ceil(span))
        left, top = camera.origin_px()
        deadline = time.perf_counter() + BUILD_MS / 1000.0
        built = 0
        for bx, by in self._visible_blocks(camera, screen.get_size(), grid):
            key = (bx, by)
            ver = grid.block_version(bx, by)
            entry = self._blocks.get(key)
            if entry is None or entry[0] != ver:
                over_budget = built and time.perf_counter() >= deadline
                if over_budget and entry is None:
                    continue                     # блока ещё не было вообще: появится на следующем кадре
                if over_budget:
                    ver, tex = entry             # бюджет выбран: пока рисуем прежнюю текстуру блока
                else:
                    tex = self._block_texture(grid, bx, by)
                    built += 1
            else:
                tex = entry[1]
            if tex is None:
                continue
            cached = self._scaled.get(key)
            if cached is None or cached[0] != ver:
                if camera.is_zooming:
                    surf = pygame.transform.scale(tex, (size, size))
                else:
                    surf = pygame.transform.smoothscale(tex, (size, size))
                    self._scaled.put(key, (ver, surf))
            else:
                surf = cached[1]
            x = round((-grid.half_w_px + bx * BLOCK_CELLS * PX_PER_M) * z) - left
            y = round((-grid.half_h_px + by * BLOCK_CELLS * PX_PER_M) * z) - top
            screen.blit(surf, (x, y))

    # ==========================================
    # КАДР
    # ==========================================
    def draw(self, screen, camera, terrain):
        self._draw_water(screen, camera, terrain.grid)

        w, h = screen.get_size()
        x0, y0 = camera.screen_to_world(0, 0)
        x1, y1 = camera.screen_to_world(w, h)
        z = camera.zoom
        for p in terrain.patches_in_rect(x0, y0, x1, y1):
            if p.kind is not ROCK:
                continue
            r = p.r_max * z
            if r < MIN_SCREEN_R:
                continue
            pts = [camera.world_to_screen(x, y) for x, y in p.pts]
            cx, cy = camera.world_to_screen(p.x, p.y)
            self._draw_rock(screen, pts, cx, cy, r)

    @staticmethod
    def _draw_rock(screen, pts, cx, cy, r):
        if r >= 4:                                                    # тень (падает вправо-вниз)
            sx, sy = r * 0.10, r * 0.14
            pygame.draw.polygon(screen, ROCK_SHADOW, [(x + sx, y + sy) for x, y in pts])
        pygame.draw.polygon(screen, ROCK_SIDE, pts)                   # боковая грань

        off = -0.06 * r                                               # верхняя грань сдвинута к свету
        top = shrink_polygon(pts, cx, cy, 0.82, off, off)
        pygame.draw.polygon(screen, ROCK_TOP, top)
        if r >= 10:                                                   # блик и грани
            lit = shrink_polygon(pts, cx, cy, 0.45, off * 2.0, off * 2.0)
            pygame.draw.polygon(screen, ROCK_LIT, lit)
            for a, b in zip(top, lit):
                pygame.draw.line(screen, ROCK_FACET, a, b, 1)
        pygame.draw.polygon(screen, ROCK_OUTLINE, pts, 1)