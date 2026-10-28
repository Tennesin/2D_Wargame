"""world/landscape.py — ландшафт карты: сетка уровней с клеткой 1 м. Без pygame.
Уровни совпадают с видами местности: 0 трава, 1 глина, 2 мелководье, 3 вода (брод), 4 глубокая вода."""
import base64
import math
import zlib

from engine import PX_PER_M, WORLD_MAX_M

CELL_PX = PX_PER_M            # размер клетки, px мира (1 м)
BLOCK_CELLS = 32              # блок для кэшей рендера: 32 x 32 клетки

L_GRASS, L_MUD, L_SHALLOWS, L_WATER, L_DEEP = 0, 1, 2, 3, 4
MAX_LEVEL = L_DEEP
_DEEPEN = (L_SHALLOWS, L_SHALLOWS, L_WATER, L_DEEP, L_DEEP)

class Landscape:
    """Матрица уровней cols x rows, строки подряд (индекс = j * cols + i).
    Начало: левый верхний угол мира (-half_w_px, -half_h_px)."""

    GRASS, MUD, SHALLOWS, WATER, DEEP = L_GRASS, L_MUD, L_SHALLOWS, L_WATER, L_DEEP

    def __init__(self, cols, rows, data=None):
        self.cols = int(cols)
        self.rows = int(rows)
        size = self.cols * self.rows
        if data is None:
            self.data = bytearray(size)
        else:
            if len(data) != size:
                raise ValueError("landscape: размер данных не совпадает с cols * rows")
            self.data = bytearray(data)
        self.half_w_px = self.cols * CELL_PX / 2.0
        self.half_h_px = self.rows * CELL_PX / 2.0
        self._ver = {}                   # (bx, by) -> версия блока (растёт при каждой правке)
        self._has_deep = None            # кэш «есть ли вообще глубокая вода»; None = пересчитать

    # ---------- служебное ----------
    @property
    def has_deep(self):
        if self._has_deep is None:
            self._has_deep = self.data.find(L_DEEP) != -1
        return self._has_deep

    def block_version(self, bx, by):
        """Версия блока: рендер пересобирает текстуру, когда она изменилась."""
        return self._ver.get((bx, by), 0)

    def _touch(self, i0, i1, j0, j1):
        """Отметить изменение клеток. Границу расширяем на клетку: текстура блока читает соседей."""
        self._has_deep = None
        i0, j0 = max(0, i0 - 1), max(0, j0 - 1)
        i1, j1 = min(self.cols - 1, i1 + 1), min(self.rows - 1, j1 + 1)
        if i1 < i0 or j1 < j0:
            return
        for by in range(j0 // BLOCK_CELLS, j1 // BLOCK_CELLS + 1):
            for bx in range(i0 // BLOCK_CELLS, i1 // BLOCK_CELLS + 1):
                key = (bx, by)
                self._ver[key] = self._ver.get(key, 0) + 1

    # ---------- координаты ----------
    def cell_range(self, x0, y0, x1, y1):
        """Диапазон клеток (i0, i1, j0, j1), накрывающих прямоугольник мира, обрезанный по карте.
        Может оказаться пустым (i1 < i0 или j1 < j0)."""
        hw, hh = self.half_w_px, self.half_h_px
        i0 = max(0, int(math.floor((x0 + hw) / CELL_PX)))
        i1 = min(self.cols - 1, int(math.floor((x1 + hw) / CELL_PX)))
        j0 = max(0, int(math.floor((y0 + hh) / CELL_PX)))
        j1 = min(self.rows - 1, int(math.floor((y1 + hh) / CELL_PX)))
        return i0, i1, j0, j1

    def cell_center(self, i, j):
        """Центр клетки (i, j) в мировых px."""
        return -self.half_w_px + (i + 0.5) * CELL_PX, -self.half_h_px + (j + 0.5) * CELL_PX

    def level_cell(self, i, j):
        if 0 <= i < self.cols and 0 <= j < self.rows:
            return self.data[j * self.cols + i]
        return L_GRASS

    def level_at(self, x, y):
        """Уровень под точкой мира; за пределами карты трава."""
        i = int((x + self.half_w_px) // CELL_PX)
        j = int((y + self.half_h_px) // CELL_PX)
        if 0 <= i < self.cols and 0 <= j < self.rows:
            return self.data[j * self.cols + i]
        return L_GRASS

    # ---------- запись ----------
    def _assign(self, j, i0, i1, level, mode):
        """Записать уровень в клетки [i0, i1) строки j. mode: "set" заменяет, "max" только повышает."""
        a = j * self.cols + i0
        b = j * self.cols + i1
        data = self.data
        if mode == "set":
            data[a:b] = bytes((level,)) * (i1 - i0)
            return
        seg = data[a:b]
        if min(seg) >= level:
            return
        if max(seg) < level:
            data[a:b] = bytes((level,)) * (i1 - i0)
        else:
            data[a:b] = bytes(v if v > level else level for v in seg)

    def fill_polygon(self, pts, level, mode="max"):
        """Закрасить клетки, центры которых лежат внутри многоугольника (мировые px).
        Построчная заливка: на каждую строку одна срезная запись, поэтому быстро."""
        if len(pts) < 3:
            return
        ox, oy = self.half_w_px, self.half_h_px
        g = [((x + ox) / CELL_PX, (y + oy) / CELL_PX) for x, y in pts]
        n = len(g)
        ymin = min(p[1] for p in g)
        ymax = max(p[1] for p in g)
        j0 = max(0, math.ceil(ymin - 0.5))
        j1 = min(self.rows - 1, math.ceil(ymax - 0.5) - 1)
        for j in range(j0, j1 + 1):
            yc = j + 0.5
            xs = []
            for k in range(n):
                xa, ya = g[k]
                xb, yb = g[(k + 1) % n]
                if (ya <= yc) != (yb <= yc):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for a in range(0, len(xs) - 1, 2):
                i0 = max(0, math.ceil(xs[a] - 0.5))
                i1 = min(self.cols, math.ceil(xs[a + 1] - 0.5))
                if i1 > i0:
                    self._assign(j, i0, i1, level, mode)
        bi0 = max(0, int(math.floor(min(p[0] for p in g))))
        bi1 = min(self.cols - 1, int(math.floor(max(p[0] for p in g))))
        self._touch(bi0, bi1, j0, j1)

    def paint_circle(self, x, y, r_px, level, mode="set"):
        """Закрасить круг (мировые px). Используется кистью редактора."""
        cx = (x + self.half_w_px) / CELL_PX
        cy = (y + self.half_h_px) / CELL_PX
        r = r_px / CELL_PX
        j0 = max(0, int(math.floor(cy - r)))
        j1 = min(self.rows - 1, int(math.ceil(cy + r)))
        lo, hi = self.cols, -1
        for j in range(j0, j1 + 1):
            dy = (j + 0.5) - cy
            if abs(dy) > r:
                continue
            half = math.sqrt(r * r - dy * dy)
            i0 = max(0, math.ceil(cx - half - 0.5))
            i1 = min(self.cols, math.ceil(cx + half - 0.5))
            if i1 > i0:
                self._assign(j, i0, i1, level, mode)
                lo, hi = min(lo, i0), max(hi, i1 - 1)
        if hi >= lo:
            self._touch(lo, hi, j0, j1)

    def deepen_circle(self, x, y, r_px, done, blocked=None):
        """Углубить круг (мировые px): каждая клетка меняется ОДИН раз за мазок. done: bytearray размером
        cols * rows, помнит клетки, уже тронутые этим мазком (его создаёт и сбрасывает инструмент).
        blocked(i, j) -> bool: сюда глубокая вода не допускается; такая клетка остаётся на уровне «вода»."""
        cols, data = self.cols, self.data
        cx = (x + self.half_w_px) / CELL_PX
        cy = (y + self.half_h_px) / CELL_PX
        r = r_px / CELL_PX
        j0 = max(0, int(math.floor(cy - r)))
        j1 = min(self.rows - 1, int(math.ceil(cy + r)))
        lo, hi = cols, -1
        for j in range(j0, j1 + 1):
            dy = (j + 0.5) - cy
            if abs(dy) > r:
                continue
            half = math.sqrt(r * r - dy * dy)
            i0 = max(0, math.ceil(cx - half - 0.5))
            i1 = min(cols, math.ceil(cx + half - 0.5))
            if i1 <= i0:
                continue
            a, b = j * cols + i0, j * cols + i1
            seen = done[a:b]
            if seen.count(0) == 0:
                continue                                   # вся полоска уже тронута
            done[a:b] = b"\x01" * (b - a)
            old = data[a:b]
            new = bytearray(old)
            for k in range(b - a):
                if seen[k]:
                    continue
                nv = _DEEPEN[old[k]]
                if nv == L_DEEP and old[k] != L_DEEP and blocked is not None and blocked(i0 + k, j):
                    nv = L_WATER
                new[k] = nv
            data[a:b] = new
            lo, hi = min(lo, i0), max(hi, i1 - 1)
        if hi >= lo:
            self._touch(lo, hi, j0, j1)

    # ---------- запросы по глубокой воде ----------
    def has_deep_in(self, i0, i1, j0, j1):
        """Есть ли глубокая вода в диапазоне клеток."""
        if not self.has_deep:
            return False
        for j in range(j0, j1 + 1):
            row = j * self.cols
            if self.data.find(L_DEEP, row + i0, row + i1 + 1) != -1:
                return True
        return False

    def deep_edges_in(self, x0, y0, x1, y1):
        """Центры «береговых» клеток глубокой воды (у которых есть недеепный сосед) в прямоугольнике мира.
        Для расстояния до воды достаточно только их: ближайшая глубокая клетка всегда береговая."""
        if not self.has_deep:
            return []
        i0, i1, j0, j1 = self.cell_range(x0, y0, x1, y1)
        out = []
        data, cols = self.data, self.cols
        for j in range(j0, j1 + 1):
            row = j * cols
            end = row + i1 + 1
            k = data.find(L_DEEP, row + i0, end)
            while k != -1:
                i = k - row
                if (self.level_cell(i - 1, j) != L_DEEP or self.level_cell(i + 1, j) != L_DEEP
                        or self.level_cell(i, j - 1) != L_DEEP or self.level_cell(i, j + 1) != L_DEEP):
                    out.append(self.cell_center(i, j))
                k = data.find(L_DEEP, k + 1, end)
        return out

    # ---------- файл ----------

    def to_dict(self):
        blob = zlib.compress(bytes(self.data), 6)
        return {"cols": self.cols, "rows": self.rows, "data": base64.b64encode(blob).decode("ascii")}

    @classmethod
    def from_dict(cls, d):
        """Ландшафт из словаря или None, если данные испорчены."""
        try:
            cols, rows, text = d["cols"], d["rows"], d["data"]
            if (isinstance(cols, bool) or isinstance(rows, bool)
                    or not isinstance(cols, int) or not isinstance(rows, int)
                    or not (1 <= cols <= WORLD_MAX_M) or not (1 <= rows <= WORLD_MAX_M)
                    or not isinstance(text, str)):
                return None
            size = cols * rows
            raw = zlib.decompressobj().decompress(base64.b64decode(text), size + 1)  # защита от «бомбы»
            if len(raw) != size or max(raw, default=0) > MAX_LEVEL:
                return None
            return cls(cols, rows, raw)
        except (KeyError, TypeError, ValueError, zlib.error):
            return None