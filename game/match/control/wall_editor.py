"""game/match/control/wall_editor.py — всё, что игрок делает со стенами: ставит, выбирает, вращает, удаляет.
О панели настроек не знает: её связывает с редактором WallPanelLink (game/content/panels/wall.py)."""
import math

from engine import shortest_angle_diff
from inputs import Action, MouseOwner
from structures import (Wall, ROTATE_HANDLE_HIT_PX, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG)
from ...config import PLACE_REPEAT
from ..modes import Mode

class WallEditor:
    def __init__(self, ctx, input_handler, modes):
        self.input = input_handler
        self.camera = ctx.camera
        self.modes = modes
        self.walls = ctx.walls
        self.fleet = ctx.fleet
        self.terrain = ctx.terrain

        self._rot_state = None           # при вращении: [последний угол мыши, накопленный угол стены]

    # ---------- клавиши ----------
    def handle_hotkeys(self):
        if self.input.was_pressed(Action.DELETE_WALL):
            self.delete_selected()

    # ---------- проверки и призрак ----------
    def is_blocked(self, wall):
        """Нельзя ли поставить стену здесь: мешает любой танк, камень или глубокая вода."""
        return self.fleet.blocks_obb(wall.obb()) or self.terrain.blocks_obb(wall.obb())

    def build_preview(self):
        """(призрак, красный ли он) или None, если показывать нечего."""
        if self.modes.mode != Mode.BUILD or not self.input.pointer_in_world:
            return None
        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)
        ghost = Wall.default(wx, wy)
        return ghost, self.is_blocked(ghost)

    # ---------- клики ----------
    def click_build(self, button, wx, wy):
        """BUILD: ЛКМ ставит стену, ПКМ выходит из стройки."""
        if button == 1:
            wall = Wall.default(wx, wy)
            if not self.is_blocked(wall):
                self.walls.add(wall)
                if not PLACE_REPEAT:
                    self.modes.set_mode(Mode.DRIVE)
        elif button == 3:
            self.modes.set_mode(Mode.DRIVE)

    def select_or_drive(self, wx, wy):
        """Стена под точкой: открыть её настройки. Пустое место: вернуться в DRIVE."""
        wall = self.walls.pick(wx, wy)
        if wall is not None:
            self.modes.set_mode(Mode.WALL_EDIT, wall)
        else:
            self.modes.set_mode(Mode.DRIVE)

    def grab_rotate(self, pos):
        """Если клик попал в белую точку выбранной стены, захватывает мышь под вращение. Возвращает True/False."""
        wall = self.walls.selected
        if wall is None:
            return False
        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        if math.hypot(pos[0] - cx, pos[1] - cy) > ROTATE_HANDLE_HIT_PX:
            return False
        self.input.grab_mouse(MouseOwner.ROTATE, 1)
        self._rot_state = None
        return True

    # ---------- удаление, параметры, вращение ----------
    def delete_selected(self):
        """Delete или красная кнопка панели: удалить выбранную стену и вернуться в DRIVE."""
        wall = self.walls.selected
        if wall is None:
            return
        self.walls.remove(wall)
        self.modes.set_mode(Mode.DRIVE)

    def apply_params(self, wall, hp, width_m, length_m):
        """Применить размеры к стене. False: новая стена упёрлась бы в технику, камень или воду,
        прежние значения возвращены (панель должна показать их же)."""
        old = (wall.max_hp, wall.width_m, wall.length_m)
        wall.apply_params(hp, width_m, length_m)
        if self.is_blocked(wall):
            wall.apply_params(*old)
            return False
        return True

    def update_rotation(self):
        """Пока мышь принадлежит ROTATE, стена поворачивается вслед за направлением мыши от её центра.
        Поворот относительный (нет рывка при захвате), с накоплением угла.
        Shift: привязка к шагу ROTATE_SNAP_DEG. Поворот, упирающийся в танк, не применяется."""
        wall = self.walls.selected
        if self.input.mouse_owner != MouseOwner.ROTATE or wall is None:
            self._rot_state = None
            return

        cx, cy = self.camera.world_to_screen(wall.x, wall.y)
        mx, my = self.input.mouse_pos
        dx, dy = mx - cx, my - cy
        if math.hypot(dx, dy) < ROTATE_DEAD_ZONE_PX:
            return                                       # мышь у самого центра: направление неопределённо
        mouse_ang = math.degrees(math.atan2(dx, -dy))    # 0 = вверх, по часовой

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

        old = wall.angle
        wall.angle = new_angle
        if self.is_blocked(wall):
            wall.angle = old