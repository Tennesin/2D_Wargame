"""world/ground_renderer.py — отрисовка земли: гладкие текстуры чанков, без декора и без ступеней детализации."""
import math
import time
import pygame

from engine import LRUCache, WORLD
from .generator import CHUNK_SIZE, GRASS_PALETTE
from .bounds_render import FADE_PX

SAMPLES = 16                # узлов цвета на сторону чанка (шаг 512 / 16 = 32 px мира)
TEX = 64                    # сторона базовой текстуры чанка, px
UP = TEX // SAMPLES         # во сколько раз smoothscale растягивает сетку узлов (TEX кратно SAMPLES)

MIN_CACHED_CHUNKS = 1200    # базовые текстуры лёгкие (16 КБ), держим с запасом, чтобы зум туда-сюда не пересчитывал
BUILD_MS = 6.0              # сколько мс за кадр можно тратить на достройку видимых чанков
PREFETCH_MS = 2.0           # и на предзагрузку кольца за краем экрана
PREFETCH_RING = 1
WIDE_PREFETCH_MS = 3.0      # бюджет мс за кадр на достройку «окна максимального отдаления»
FALLBACK_COLOR = (102, 148, 74)   # средняя трава: показывается на месте чанка, который не успели построить
FLAT_SPAN_PX = 40.0         # чанк мельче этого на экране: земля одной заливкой (дальний зум редактора)

class GroundRenderer:
    def __init__(self, world_generator, wide=False):
        self.world = world_generator
        self.wide = wide                  # True: держать готовым всё, что видно при самом далёком зуме
        self._chunk_cache = LRUCache()
        self._scaled_cache = LRUCache()
        self._wide_key = None             # окно, для которого уже проверяли чанки
        self._wide_done = False           # все чанки этого окна уже в кэше

    def set_zoom(self):
        """Зум сменился: масштабированные чанки устарели, базовые остаются."""
        self._scaled_cache.clear()

    # ==========================================
    # КАДР
    # ==========================================
    def draw(self, screen, camera):
        if CHUNK_SIZE * camera.zoom < FLAT_SPAN_PX:
            screen.fill(FALLBACK_COLOR)
            return
        rng = self._visible_range(camera, screen.get_size())
        if rng is None:
            return                                        # на экране только глухая темнота
        cx0, cx1, cy0, cy1 = rng
        left, top = camera.origin_px()
        span = CHUNK_SIZE * camera.zoom                   # размер чанка на экране (дробный)
        size = math.ceil(span)                            # заготовка чуть больше шага: швов нет

        coords = [(cx, cy) for cy in range(cy0, cy1 + 1) for cx in range(cx0, cx1 + 1)]
        bases = {c: self._chunk_cache.get(c) for c in coords}
        missing = [c for c, base in bases.items() if base is None]

        if missing:                                       # достраиваем в рамках бюджета, ближние к центру первыми
            mid_x = (left + screen.get_width() / 2.0) / span - 0.5
            mid_y = (top + screen.get_height() / 2.0) / span - 0.5
            missing.sort(key=lambda c: (c[0] - mid_x) ** 2 + (c[1] - mid_y) ** 2)
            deadline = time.perf_counter() + BUILD_MS / 1000.0
            built = 0
            for c in missing:
                if built and time.perf_counter() >= deadline:
                    break
                bases[c] = self._get_chunk(*c)
                built += 1
            if built < len(missing):
                screen.fill(FALLBACK_COLOR)               # недостроенные места пока залиты средним цветом

        for (cx, cy), base in bases.items():
            if base is None:
                continue
            tile = self._get_scaled_chunk(cx, cy, base, size)
            screen.blit(tile, (round(cx * span) - left, round(cy * span) - top))

        if self.wide:
            ring = self._prefetch_wide(camera, screen.get_size())
            keep = ring                                    # окно уже включает видимые чанки
        else:
            ring = self._prefetch(cx0, cx1, cy0, cy1)
            keep = len(coords) + ring
        self._chunk_cache.trim(max(MIN_CACHED_CHUNKS, keep + 12))
        self._scaled_cache.trim(max(40, len(coords) + 12))

    def preload_iter(self, camera, size):
        """Строит чанки по одному."""
        if self.wide:
            rng = self._wide_range(camera, size)
            if rng is None:
                return
            x0, x1, y0, y1 = rng
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            coords = sorted(((cx, cy) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)),
                            key=lambda c: (c[0] - mx) ** 2 + (c[1] - my) ** 2)
        else:
            rng = self._visible_range(camera, size)
            if rng is None:
                return
            cx0, cx1, cy0, cy1 = rng
            lx0, lx1, ly0, ly1 = self._chunk_limits()
            coords = [(cx, cy)
                      for cy in range(max(cy0 - PREFETCH_RING, ly0), min(cy1 + PREFETCH_RING, ly1) + 1)
                      for cx in range(max(cx0 - PREFETCH_RING, lx0), min(cx1 + PREFETCH_RING, lx1) + 1)]
        for n, (cx, cy) in enumerate(coords, 1):
            self._get_chunk(cx, cy)
            yield n / len(coords)

    def preload(self, camera, size):
        """Синхронно строит всё, что видно сейчас, и кольцо вокруг."""
        for _ in self.preload_iter(camera, size):
            pass

    # ==========================================
    # ЧАНКИ
    # ==========================================
    @staticmethod
    def _chunk_limits():
        """Диапазон номеров чанков, которые вообще бывают видны: мир + зона затемнения."""
        mx = WORLD.half_w_px + FADE_PX
        my = WORLD.half_h_px + FADE_PX
        return (math.floor(-mx / CHUNK_SIZE), math.floor(mx / CHUNK_SIZE),
                math.floor(-my / CHUNK_SIZE), math.floor(my / CHUNK_SIZE))

    def _visible_range(self, camera, size):
        """(cx0, cx1, cy0, cy1) видимых чанков, обрезанных по миру, или None."""
        left, top = camera.origin_px()
        width, height = size
        span = CHUNK_SIZE * camera.zoom
        cx0 = math.floor(left / span)
        cx1 = math.floor((left + width - 1) / span)
        cy0 = math.floor(top / span)
        cy1 = math.floor((top + height - 1) / span)
        lx0, lx1, ly0, ly1 = self._chunk_limits()
        cx0, cx1 = max(cx0, lx0), min(cx1, lx1)
        cy0, cy1 = max(cy0, ly0), min(cy1, ly1)
        if cx0 > cx1 or cy0 > cy1:
            return None
        return cx0, cx1, cy0, cy1

    def _prefetch(self, cx0, cx1, cy0, cy1):
        """Готовит чанки в кольце за краем экрана. Возвращает, сколько их в кольце (для лимита кэша)."""
        deadline = time.perf_counter() + PREFETCH_MS / 1000.0
        out_of_time = False
        count = 0
        lx0, lx1, ly0, ly1 = self._chunk_limits()
        for cy in range(max(cy0 - PREFETCH_RING, ly0), min(cy1 + PREFETCH_RING, ly1) + 1):
            for cx in range(max(cx0 - PREFETCH_RING, lx0), min(cx1 + PREFETCH_RING, lx1) + 1):
                if cx0 <= cx <= cx1 and cy0 <= cy <= cy1:
                    continue
                count += 1
                if self._chunk_cache.get((cx, cy)) is not None:
                    continue
                if out_of_time or time.perf_counter() >= deadline:
                    out_of_time = True
                    continue
                self._get_chunk(cx, cy)
        return count

    def _wide_range(self, camera, size):
        """(cx0, cx1, cy0, cy1) чанков, видимых при самом далёком зуме вокруг центра камеры
        (плюс кольцо), обрезанных по миру. None, если смотреть не на что."""
        # ниже порога FLAT_SPAN_PX земля рисуется одной заливкой, строить её незачем
        zmin = max(camera.zoom_min, FLAT_SPAN_PX / CHUNK_SIZE)
        span = CHUNK_SIZE * zmin
        w, h = size
        left = camera.x * zmin - w / 2.0
        top = camera.y * zmin - h / 2.0
        lx0, lx1, ly0, ly1 = self._chunk_limits()
        cx0 = max(math.floor(left / span) - PREFETCH_RING, lx0)
        cx1 = min(math.floor((left + w - 1) / span) + PREFETCH_RING, lx1)
        cy0 = max(math.floor(top / span) - PREFETCH_RING, ly0)
        cy1 = min(math.floor((top + h - 1) / span) + PREFETCH_RING, ly1)
        if cx0 > cx1 or cy0 > cy1:
            return None
        return cx0, cx1, cy0, cy1

    def _prefetch_wide(self, camera, size):
        """Достраивает окно максимального отдаления в рамках WIDE_PREFETCH_MS, ближние чанки первыми."""
        rng = self._wide_range(camera, size)
        if rng is None:
            return 0
        x0, x1, y0, y1 = rng
        total = (x1 - x0 + 1) * (y1 - y0 + 1)
        if rng == self._wide_key and self._wide_done:
            return total
        cache = self._chunk_cache
        missing = [(cx, cy) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)
                   if cache.get((cx, cy)) is None]
        self._wide_key = rng
        self._wide_done = not missing
        if missing:
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            missing.sort(key=lambda c: (c[0] - mx) ** 2 + (c[1] - my) ** 2)
            deadline = time.perf_counter() + WIDE_PREFETCH_MS / 1000.0
            for c in missing:
                if time.perf_counter() >= deadline:
                    break
                self._get_chunk(*c)
        return total

    def _get_scaled_chunk(self, cx, cy, base, size):
        key = (cx, cy)
        tile = self._scaled_cache.get(key)
        if tile is None:
            tile = pygame.transform.scale(base, (size, size))   # текстура уже гладкая: быстрого масштабирования хватает
            self._scaled_cache.put(key, tile)
        return tile

    def _get_chunk(self, cx, cy):
        return self._chunk_cache.get_or_build((cx, cy), lambda: self._build_chunk(cx, cy))

    def _build_chunk(self, cx, cy):
        """Сетка цветов (с запасом в один узел по краям) -> smoothscale -> вырезаем центр.
        Узлы соседних чанков лежат в одних и тех же точках мира, поэтому стыки незаметны."""
        step = CHUNK_SIZE / SAMPLES
        count = SAMPLES + 2
        grid = self.world.grass_grid(cx * CHUNK_SIZE - step / 2.0, cy * CHUNK_SIZE - step / 2.0,
                                     step, count)
        small = pygame.Surface((count, count), 0, 32)
        last = len(GRASS_PALETTE) - 1
        for j, row in enumerate(grid):
            for i, g in enumerate(row):
                small.set_at((i, j), GRASS_PALETTE[int(g * last + 0.5)])
        big = pygame.transform.smoothscale(small, (count * UP, count * UP))
        return big.subsurface((UP, UP, TEX, TEX)).copy().convert()