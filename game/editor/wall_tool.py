"""game/editor/wall_tool.py — инструмент «Стена» редактора карт: ставит, выбирает, поворачивает и удаляет стены.
О панели настроек не знает: с ней его связывает WallPanelLink (game/content/panels/wall.py)."""
import math

from engine import PX_PER_M, shortest_angle_diff, obb_distance_to_point
from inputs import MouseOwner
from structures import Wall, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG
from world import START_CLEAR_M
from . import gizmo

PICK_TOL_PX = 6.0            # допуск выбора стены, экранные px (на дальнем зуме стена очень тонкая)

class WallTool:
    def __init__(self, camera, input_handler, walls, terrain, on_change=None):
        self.camera = camera
        self.input = input_handler
        self.walls = walls                 # WallManager; walls.selected: выбранная стена
        self.terrain = terrain
        self.on_change = on_change         # колбэк(): карта изменилась
        self.on_select = None              # колбэк(wall или None): выбор изменился
        self.get_params = None             # функция() -> {"wall_hp", "wall_width_m", "wall_length_m"}
        self._rot_state = None             # при вращении: [последний угол мыши, накопленный угол стены]
        self._move_off = None              # при перемещении: смещение (центр стены - точка захвата), мировые px

    # ---------- внутреннее ----------
    def _changed(self):
        if self.on_change is not None:
            self.on_change()

    def _new_wall(self, x, y):
        if self.get_params is None:
            return Wall.default(x, y)
        p = self.get_params()
        return Wall(x, y, p["wall_hp"], p["wall_width_m"], p["wall_length_m"])

    def _pick(self, wx, wy):
        """Верхняя стена под точкой с допуском в экранных px или None."""
        tol = PICK_TOL_PX / self.camera.zoom
        best = None
        for wall in self.walls.near_walls(wx, wy, tol):
            if obb_distance_to_point(wall.obb(), wx, wy) <= tol and (best is None or wall.z > best.z):
                best = wall
        return best

    def is_blocked(self, wall):
        """Нельзя ли поставить стену здесь: стартовая зона, камень, глубокая вода, край карты."""
        obb = wall.obb()
        if obb_distance_to_point(obb, 0.0, 0.0) < START_CLEAR_M * PX_PER_M:
            return True
        return self.terrain.blocks_obb(obb)

    # ---------- призрак ----------
    def preview(self):
        """(призрак, красный ли он) или None."""
        if self.walls.selected is not None or not self.input.pointer_in_world:
            return None
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        if self._pick(wx, wy) is not None:
            return None
        ghost = self._new_wall(wx, wy)
        return ghost, self.is_blocked(ghost)

    # ---------- выбор ----------
    def select(self, wall):
        self.walls.selected = wall
        self._rot_state = None
        self._move_off = None
        if self.on_select is not None:
            self.on_select(wall)

    def deselect(self):
        self.walls.selected = None
        self._rot_state = None
        self._move_off = None
        self.input.release_mouse(MouseOwner.ROTATE)
        self.input.release_mouse(MouseOwner.MOVE)
        if self.on_select is not None:
            self.on_select(None)

    # ---------- клики ----------
    def click(self, button, pos, wx, wy):
        """ЛКМ: белая точка выбранной стены, затем выбор стены под курсором,
        иначе (если ничего не выбрано) постановка новой. ПКМ снимает выбор."""
        if button == 3:
            self.deselect()
            return
        if button != 1:
            return
        if self.grab_handle(pos):
            return
        wall = self._pick(wx, wy)
        if wall is not None:
            self.select(wall)
        elif self.walls.selected is not None:
            self.deselect()
        else:
            new = self._new_wall(wx, wy)
            if not self.is_blocked(new):
                self.walls.add(new)
                self._changed()

    @property
    def drag_mode(self):
        """"move", "rotate" или None: что сейчас тянут за ручку."""
        owner = self.input.mouse_owner
        if owner is MouseOwner.MOVE:
            return "move"
        if owner is MouseOwner.ROTATE:
            return "rotate"
        return None

    def gizmo_geom(self):
        """(x, y центра на экране, радиус дуг, угол) выбранной стены или None."""
        wall = self.walls.selected
        if wall is None:
            return None
        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        extent = wall.radius_px * self.camera.zoom          # половина диагонали стены на экране
        return cx, cy, gizmo.arc_radius(extent), wall.angle

    def grab_handle(self, pos):
        """Клик попал в точку (двигать) или в дугу (вращать): мышь закрепляется за нужным владельцем."""
        geom = self.gizmo_geom()
        wall = self.walls.selected
        if geom is None or wall is None:
            return False
        mode = gizmo.hit(*geom, pos)
        if mode is None:
            return False
        owner = MouseOwner.MOVE if mode == "move" else MouseOwner.ROTATE
        if not self.input.grab_mouse(owner, 1):
            return False
        self._rot_state = None
        self._move_off = None
        if mode == "move":
            wx, wy = self.camera.screen_to_world(*pos)
            self._move_off = (wall.x - wx, wall.y - wy)
        return True

    # ---------- правка ----------
    def delete_selected(self):
        wall = self.walls.selected
        if wall is None:
            return
        self.walls.remove(wall)
        self.deselect()
        self._changed()

    def apply_params(self, values):
        """Ползунки панели -> выбранная стена."""
        wall = self.walls.selected
        if wall is None:
            return True
        old = (wall.max_hp, wall.width_m, wall.length_m)
        wall.apply_params(values["wall_hp"], values["wall_width_m"], values["wall_length_m"])
        if self.is_blocked(wall):
            wall.apply_params(*old)
            return False
        self._changed()
        return True

    def update_rotation(self):
        """Пока мышь принадлежит ROTATE, стена поворачивается за направлением мыши от её центра."""
        wall = self.walls.selected
        if self.input.mouse_owner != MouseOwner.ROTATE or wall is None:
            self._rot_state = None
            return
        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        mx, my = self.input.mouse_pos
        dx, dy = mx - cx, my - cy
        if math.hypot(dx, dy) < ROTATE_DEAD_ZONE_PX:
            return
        mouse_ang = math.degrees(math.atan2(dx, -dy))        # 0 = вверх, по часовой

        if self._rot_state is None:
            self._rot_state = [mouse_ang, wall.angle]
            return
        last, raw = self._rot_state
        raw += shortest_angle_diff(mouse_ang, last)
        self._rot_state = [mouse_ang, raw]

        new_angle = raw
        if self.input.shift:
            new_angle = round(raw / ROTATE_SNAP_DEG) * ROTATE_SNAP_DEG
        new_angle %= 360.0
        if new_angle == wall.angle:
            return
        old = wall.angle
        wall.angle = new_angle
        if self.is_blocked(wall):
            wall.angle = old
        else:
            self._changed()

    def update_move(self):
        """Пока мышь принадлежит MOVE, стена едет за курсором."""
        wall = self.walls.selected
        if self.input.mouse_owner is not MouseOwner.MOVE or wall is None or self._move_off is None:
            self._move_off = None
            return
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        nx, ny = round(wx + self._move_off[0], 1), round(wy + self._move_off[1], 1)
        if (nx, ny) == (wall.x, wall.y):
            return
        old = (wall.x, wall.y)
        wall.x, wall.y = nx, ny              # временно, только для проверки (индекс пока не трогаем)
        blocked = self.is_blocked(wall)
        wall.x, wall.y = old
        if blocked:
            return
        self.walls.move_to(wall, nx, ny)
        self._changed()