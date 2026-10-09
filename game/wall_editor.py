"""game/wall_editor.py — всё, что игрок делает со стенами: ставит, выбирает, вращает, удаляет."""
import math

from engine import shortest_angle_diff, fmt_num
from inputs import Action, MouseOwner
from structures import (Wall, PLACE_REPEAT,
                        ROTATE_HANDLE_HIT_PX, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG)
from .modes import Mode
from .panels import PanelMode, wall_values, bind_wall_delete

class WallEditor:
    def __init__(self, input_handler, camera, modes, walls, tank, terrain, ui):
        self.input = input_handler
        self.camera = camera
        self.modes = modes
        self.walls = walls
        self.tank = tank
        self.terrain = terrain
        self.ui = ui

        self._rot_state = None           # при вращении: [последний угол мыши, накопленный угол стены]
        self._stats_key = None           # последние показанные значения стены

        ui.set_on_change(PanelMode.WALL, self.on_params_change)
        bind_wall_delete(ui, self.delete_selected)

    # ---------- клавиши ----------
    def handle_hotkeys(self):
        if self.input.was_pressed(Action.DELETE_WALL):
            self.delete_selected()

    # ---------- проверки и призрак ----------
    def is_blocked(self, wall):
        """Нельзя ли поставить стену здесь: мешает танк, камень или глубокая вода."""
        return self.tank.hits_obb(wall.obb()) or self.terrain.blocks_obb(wall.obb())

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

    # ---------- удаление, ползунки, вращение ----------
    def delete_selected(self):
        """Delete или красная кнопка панели: удалить выбранную стену и вернуться в DRIVE."""
        wall = self.walls.selected
        if wall is None:
            return
        self.walls.remove(wall)
        self.modes.set_mode(Mode.DRIVE)

    def on_params_change(self, values):
        """Ползунок стены сдвинут. Если новая стена упёрлась бы в танк, возвращаем прежние значения."""
        wall = self.walls.selected
        if wall is None:
            return
        old = (wall.max_hp, wall.width_m, wall.length_m)
        wall.apply_params(values["wall_hp"], values["wall_width_m"], values["wall_length_m"])
        if self.tank.hits_obb(wall.obb()):
            wall.apply_params(*old)
            self.ui.set_values(PanelMode.WALL, wall_values(wall))

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
        if self.tank.hits_obb(wall.obb()):
            wall.angle = old

    # ---------- статистика ----------
    def update_stats(self):
        """Пишем в панель только в режиме WALL_EDIT и только если значения изменились."""
        wall = self.walls.selected
        if wall is None or self.modes.mode != Mode.WALL_EDIT:
            return
        key = (wall.hp, wall.max_hp, wall.width_m, wall.length_m, wall.angle)
        if key == self._stats_key:
            return
        self._stats_key = key
        self.ui.set_stat("Текущее HP", f"{fmt_num(wall.hp)} / {fmt_num(wall.max_hp)}")
        self.ui.set_stat("Масса стены", f"{fmt_num(wall.mass_t, 1)} т")
        self.ui.set_stat("Толщина", f"{wall.thickness_m:.2f} м")
        self.ui.set_stat("Эквивалент брони", f"{wall.armor_mm:.0f} мм")
        self.ui.set_stat("Угол", f"{wall.angle:.0f} °")