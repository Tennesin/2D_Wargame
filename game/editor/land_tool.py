"""game/editor/land_tool.py — инструмент «Ландшафт» редактора карт: кисть для равнины, глины и воды.
Мазок держит за собой мышь (MouseOwner.PAINT). Углубления: клетка меняется один раз за мазок."""
import math

from engine import PX_PER_M, obb_hits_convex, obb_hits_obb
from inputs import MouseOwner
from world import START_CLEAR_M, L_GRASS, L_MUD, L_SHALLOWS
from world.landscape import CELL_PX

BIOME_LEVEL = {"plain": L_GRASS, "mud": L_MUD, "water": L_SHALLOWS}
CELL_HALF = CELL_PX / 2.0
CELL_REACH = CELL_HALF * 1.4143          # от центра клетки до её угла
STEP_K = 0.5                             # шаг штампов вдоль мазка: доля радиуса кисти
MAX_STAMPS = 400                         # страховка, если мышь «прыгнула» через всю карту
MOVE_EPS_PX = 0.5                        # сдвиг мыши меньше этого мазком не считается

class LandTool:
    def __init__(self, camera, input_handler, walls, terrain, on_change=None):
        self.camera = camera
        self.input = input_handler
        self.walls = walls
        self.terrain = terrain
        self.grid = terrain.grid
        self.on_change = on_change
        self.get_params = None            # функция() -> значения ползунков (ставит LandPanelLink)
        self._active = False
        self._last = None                 # последняя точка мазка (мировые px)
        self._done = None                 # bytearray: клетки, уже углублённые этим мазком
        self._touched = False
        self._rocks = []                  # препятствия рядом со штампом (для запрета глубокой воды)
        self._wall_obbs = []

    # ---------- параметры ----------
    def params(self):
        """(покрытие, радиус кисти в px, углублять ли)."""
        p = self.get_params() if self.get_params is not None else {}
        biome = p.get("land_biome", "plain")
        radius = p.get("land_radius_m", 5.0) * PX_PER_M
        deepen = biome == "water" and p.get("land_deepen", "off") == "on"
        return biome, radius, deepen

    def cursor(self):
        """(x, y, радиус px, ключ цвета) для круга кисти или None, если курсор не над миром."""
        if not self.input.pointer_in_world:
            return None
        biome, r, deepen = self.params()
        x, y = self.camera.screen_to_world(*self.input.mouse_pos)
        return x, y, r, ("deep" if deepen else biome)

    # ---------- клики и мазок ----------
    def click(self, button, pos, wx, wy):
        """ЛКМ начинает мазок; закрепляет мышь, пока кнопка зажата."""
        if button != 1 or self._active:
            return
        if self.input.grab_mouse(MouseOwner.PAINT, 1):
            self._active = True
            self._last = None
            self._done = None
            self._stamp_to(wx, wy)

    def update_stroke(self):
        """Каждый кадр: продолжить мазок или закончить, если кнопку отпустили."""
        if not self._active:
            return
        if self.input.mouse_owner is not MouseOwner.PAINT:
            self.cancel()
            return
        if self.input.mouse_over_ui:
            self._last = None                    # ушли на панель: линию к возврату не тянем
        else:
            wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
            if self._last is None or math.hypot(wx - self._last[0], wy - self._last[1]) * self.camera.zoom > MOVE_EPS_PX:
                self._stamp_to(wx, wy)
        self._flush()

    def cancel(self):
        """Закончить мазок (отпустили кнопку, сменили инструмент, открылось окно)."""
        if self._active:
            self._active = False
            self._done = None
            self._last = None
            self._flush()
        self.input.release_mouse(MouseOwner.PAINT)

    def _flush(self):
        if self._touched:
            self._touched = False
            if self.on_change is not None:
                self.on_change()

    # ---------- штампы ----------
    def _stamp_to(self, x, y):
        biome, r, deepen = self.params()
        if self._last is None:
            points = [(x, y)]
        else:
            lx, ly = self._last
            step = max(CELL_PX, r * STEP_K)
            n = max(1, min(MAX_STAMPS, math.ceil(math.hypot(x - lx, y - ly) / step)))
            points = [(lx + (x - lx) * k / n, ly + (y - ly) * k / n) for k in range(1, n + 1)]
        for px, py in points:
            self._stamp(px, py, biome, r, deepen)
        self._last = (x, y)

    def _stamp(self, x, y, biome, r, deepen):
        if deepen:
            if self._done is None:
                self._done = bytearray(self.grid.cols * self.grid.rows)
            reach = r + CELL_PX
            self._rocks = [p for p in self.terrain.patches_near(x, y, reach) if p.kind.solid]
            self._wall_obbs = self.walls.obbs_near(x, y, reach)
            self.grid.deepen_circle(x, y, r, self._done, self._cell_blocked)
        else:
            self.grid.paint_circle(x, y, r, BIOME_LEVEL[biome], "set")
        self._touched = True

    def _cell_blocked(self, i, j):
        """Нельзя ли сделать клетку глубокой: стартовая зона, камень или стена."""
        cx, cy = self.grid.cell_center(i, j)
        if math.hypot(cx, cy) < START_CLEAR_M * PX_PER_M + CELL_REACH:
            return True
        for p in self._rocks:
            dx, dy = p.x - cx, p.y - cy
            lim = p.r_max + CELL_REACH
            if dx * dx + dy * dy <= lim * lim and any(
                    obb_hits_convex(cx, cy, CELL_HALF, CELL_HALF, 0.0, tri) for tri in p.tris):
                return True
        for ox, oy, hw, hl, ang in self._wall_obbs:
            if obb_hits_obb(cx, cy, CELL_HALF, CELL_HALF, 0.0, ox, oy, hw, hl, ang):
                return True
        return False