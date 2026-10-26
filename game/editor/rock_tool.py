"""game/editor/rock_tool.py — инструмент «Камень» редактора карт: ставит, выбирает и удаляет камни.
О панели настроек не знает: с ней его связывает RockPanelLink (game/content/panels/rock.py)."""
import math
import random

from engine import PX_PER_M, obb_hits_convex
from world import Patch, ROCK, RockData, START_CLEAR_M, ROCK_PARAMS, make_rock_points

PICK_TOL_PX = 6.0            # допуск выбора камня, экранные px

def dist_to_patch(p, x, y):
    """Расстояние от точки до камня: 0 внутри, иначе до ближайшего ребра."""
    if p.contains(x, y):
        return 0.0
    best = float("inf")
    ax, ay = p.pts[-1]
    for bx, by in p.pts:
        abx, aby = bx - ax, by - ay
        ln = abx * abx + aby * aby
        t = 0.0 if ln <= 1e-9 else max(0.0, min(1.0, ((x - ax) * abx + (y - ay) * aby) / ln))
        best = min(best, math.hypot(ax + abx * t - x, ay + aby * t - y))
        ax, ay = bx, by
    return best

class RockTool:
    def __init__(self, camera, input_handler, walls, terrain, on_change=None):
        self.camera = camera
        self.input = input_handler
        self.walls = walls
        self.terrain = terrain
        self.on_change = on_change         # колбэк(): карта изменилась
        self.on_select = None              # колбэк(Patch или None): выбор изменился (ставит RockPanelLink)
        self.get_params = None             # функция() -> значения ползунков (ставит RockPanelLink)
        self.selected = None               # выбранный камень (Patch)
        self._seed = random.randrange(1 << 30)    # зерно формы у курсора; после установки меняется
        self._shape_key = None
        self._shape_pts = []

    # ---------- форма ----------
    def _params(self):
        if self.get_params is not None:
            return self.get_params()
        return {k: p.default for k, p in ROCK_PARAMS.items()}

    def _shape(self):
        """Форма камня вокруг (0, 0). Пока зерно и ползунки те же, форма не меняется."""
        p = self._params()
        key = (self._seed, p["rock_radius_m"], p["rock_stability"], p["rock_smooth"])
        if key != self._shape_key:
            self._shape_key = key
            self._shape_pts = make_rock_points(random.Random(self._seed), p["rock_radius_m"] * PX_PER_M,
                                               p["rock_stability"], p["rock_smooth"])
        return self._shape_pts

    def _ghost(self, x, y):
        return Patch(ROCK, x, y, [(x + px, y + py) for px, py in self._shape()])

    def _changed(self):
        if self.on_change is not None:
            self.on_change()

    # ---------- проверки ----------
    def is_blocked(self, patch):
        """Нельзя ли поставить камень: стартовая зона, край карты, глубокая вода, стена."""
        clear = START_CLEAR_M * PX_PER_M
        if math.hypot(patch.x, patch.y) - patch.r_max < clear and dist_to_patch(patch, 0.0, 0.0) < clear:
            return True
        hw, hh = self.terrain.half_w, self.terrain.half_h
        if any(abs(px) > hw or abs(py) > hh for px, py in patch.pts):
            return True
        if self.terrain.deep_overlaps(patch):
            return True
        for ox, oy, ohw, ohl, ang in self.walls.obbs_near(patch.x, patch.y, patch.r_max):
            if any(obb_hits_convex(ox, oy, ohw, ohl, ang, tri) for tri in patch.tris):
                return True
        return False

    def _pick(self, wx, wy):
        """Камень под точкой (с допуском в экранных px) или None."""
        tol = PICK_TOL_PX / self.camera.zoom
        best, best_d = None, None
        for p in self.terrain.patches_near(wx, wy, tol):
            if p.kind is not ROCK:
                continue
            d = dist_to_patch(p, wx, wy)
            if d <= tol and (best_d is None or d <= best_d):
                best, best_d = p, d
        return best

    # ---------- призрак ----------
    def preview(self):
        """(призрак, красный ли он) или None: нет призрака, пока выбран камень, курсор над
        интерфейсом или над уже стоящим камнем."""
        if self.selected is not None or not self.input.pointer_in_world:
            return None
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        if self._pick(wx, wy) is not None:
            return None
        ghost = self._ghost(wx, wy)
        return ghost, self.is_blocked(ghost)

    # ---------- выбор ----------
    def select(self, rock):
        self.selected = rock
        if self.on_select is not None:
            self.on_select(rock)

    def deselect(self):
        self.selected = None
        if self.on_select is not None:
            self.on_select(None)

    # ---------- клики ----------
    def click(self, button, pos, wx, wy):
        """ЛКМ: камень под курсором выбирается; пустое место при выбранном камне снимает выбор,
        иначе ставит новый камень. ПКМ: выбирает камень под курсором или снимает выбор."""
        rock = self._pick(wx, wy)
        if button == 3:
            self.select(rock) if rock is not None else self.deselect()
        elif button == 1:
            if rock is not None:
                self.select(rock)
            elif self.selected is not None:
                self.deselect()
            else:
                self._place(wx, wy)

    def _place(self, wx, wy):
        cx, cy = round(wx, 1), round(wy, 1)
        ghost = self._ghost(cx, cy)
        if self.is_blocked(ghost):
            return
        data = RockData(cx, cy, [(round(x, 1), round(y, 1)) for x, y in ghost.pts])
        self.terrain.add_rock(data)
        self._seed = random.randrange(1 << 30)       # следующий камень будет другой формы
        self._changed()

    # ---------- удаление ----------
    def delete_selected(self):
        """Удаляет выбранный камень. True, если что-то удалено."""
        rock = self.selected
        if rock is None:
            return False
        self.deselect()
        self.terrain.remove_rock(rock)
        self._changed()
        return True

    def delete_hovered(self):
        """Delete без выбора: удаляет камень под курсором."""
        if not self.input.pointer_in_world:
            return False
        rock = self._pick(*self.camera.screen_to_world(*self.input.mouse_pos))
        if rock is None:
            return False
        self.terrain.remove_rock(rock)
        self._changed()
        return True