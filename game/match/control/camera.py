"""game/match/control/camera.py — зум, размер окна, свободная камера, следование за танком
и плавное смещение обзора в сторону курсора."""
import math
import pygame

from inputs import Action, MouseOwner
from ...config import LOOK_AHEAD

PAN_DRAG_THRESHOLD_PX = 5     # на сколько px надо сдвинуть мышь с зажатой ПКМ, чтобы это считалось перетаскиванием

# --- смещение обзора к курсору ---
LOOK_DEADZONE = 0.25          # доля полуразмера экрана вокруг центра, где цель смещения равна нулю
LOOK_ACCEL = 1.0              # разгон и торможение камеры, доли экрана в секунду за секунду
LOOK_VMAX = 0.4               # потолок скорости камеры, доли экрана в секунду
LOOK_MARGIN_PX = 150          # на сколько px от края экрана танк остаётся при максимальном смещении

def _dead(n, zone):
    """Нормированное отклонение n (-1..1) с вырезанной мёртвой зоной; результат снова -1..1."""
    a = abs(n)
    if a <= zone:
        return 0.0
    return math.copysign(min(1.0, (a - zone) / (1.0 - zone)), n)

class CameraController:
    def __init__(self, camera, input_handler):
        self.camera = camera
        self.input = input_handler
        self.free_camera = False         # свободная камера (L): не следует за танком
        self._pan = None                 # при нажатой ПКМ: {"start", "last", "dragged"}
        self._target = [0.0, 0.0]        # куда тянется обзор: доли экрана -1..1 (по X и Y)
        self._look = [0.0, 0.0]          # текущее сглаженное смещение, те же доли экрана
        self._vel = [0.0, 0.0]           # скорость смещения, доли экрана в секунду

    # ---------- клавиши ----------
    def handle_hotkeys(self):
        if self.input.was_pressed(Action.TOGGLE_FREE_CAM):
            self.set_free(not self.free_camera)

    def set_free(self, on):
        """При включении камера остаётся там, где была; при выключении возвращается к танку."""
        self.free_camera = on
        self._pan = None
        self.input.release_mouse(MouseOwner.PAN)

    # ---------- каждый кадр ----------
    def update_view(self, dt, size):
        """Зум (колёсико и клавиши) и размер окна."""
        self.input.update_zoom_keys(dt)
        steps = self.input.pop_zoom_steps()
        if steps:
            self.camera.zoom_by(steps)
        self.camera.resize(*size)

    def follow(self, tank, dt=0.0):
        """Центр камеры = корпус танка + сглаженное смещение в сторону курсора."""
        if self.free_camera:
            return
        hx, hy = tank.hull_obb()[:2]
        ox, oy = self._look_offset(dt)
        self.camera.center_on(hx + ox, hy + oy)

    # ---------- смещение обзора ----------
    def _update_target(self):
        """Цель смещения берётся из положения мыши. Если курсор не работает на мир
        (над интерфейсом, вращение стены) или вне окна, прежняя цель сохраняется."""
        if not LOOK_AHEAD:
            self._target[0] = self._target[1] = 0.0
            return
        if not self.input.pointer_in_world or not pygame.mouse.get_focused():
            return
        cam = self.camera
        half_w, half_h = cam.view_w / 2.0, cam.view_h / 2.0
        if half_w <= 0 or half_h <= 0:
            return
        mx, my = self.input.mouse_pos
        self._target[0] = _dead((mx - half_w) / half_w, LOOK_DEADZONE)
        self._target[1] = _dead((my - half_h) / half_h, LOOK_DEADZONE)

    def _look_offset(self, dt):
        """Смещение камеры от корпуса, мировые px.
        У смещения есть скорость: она растёт под действием ускорения и гаснет по мере приближения
        к цели (допустимая скорость sqrt(2*A*d) гарантирует остановку точно в цели).
        Работает в долях экрана, поэтому смена зума и окна рывка не даёт."""
        self._update_target()
        if dt > 0.0:
            for i in (0, 1):
                self._step_axis(i, dt)

        cam = self.camera
        z = cam.zoom
        max_x = max(0.0, (cam.view_w / 2.0 - LOOK_MARGIN_PX) / z)
        max_y = max(0.0, (cam.view_h / 2.0 - LOOK_MARGIN_PX) / z)
        return self._look[0] * max_x, self._look[1] * max_y

    def _step_axis(self, i, dt):
        """Один шаг разгона/торможения по оси i."""
        diff = self._target[i] - self._look[i]
        vel = self._vel[i]

        # цель достигнута и скорость почти нулевая: фиксируемся, чтобы не дрожать у цели
        if abs(diff) < 1e-4 and abs(vel) < 1e-3:
            self._look[i] = self._target[i]
            self._vel[i] = 0.0
            return

        # желаемая скорость: в сторону цели, не выше потолка и не выше той, с которой ещё успеем затормозить
        allowed = min(LOOK_VMAX, math.sqrt(2.0 * LOOK_ACCEL * abs(diff)))
        want = math.copysign(allowed, diff)

        # скорость меняется только на LOOK_ACCEL * dt за кадр (и при разгоне, и при торможении)
        dv = want - vel
        max_dv = LOOK_ACCEL * dt
        if abs(dv) > max_dv:
            dv = math.copysign(max_dv, dv)
        vel += dv

        move = vel * dt
        # защита от перелёта: если за кадр проскочили цель, ставим точно в неё
        if diff * (diff - move) <= 0.0:
            self._look[i] = self._target[i]
            self._vel[i] = 0.0
            return

        self._look[i] += move
        self._vel[i] = vel

    # ---------- перетаскивание ПКМ ----------
    def begin_pan(self, pos):
        """ПКМ нажата при свободной камере: мышь закрепляется за PAN, решение «клик или drag» принимается позже."""
        if self.input.grab_mouse(MouseOwner.PAN, 3):
            self._pan = {"start": pos, "last": pos, "dragged": False}

    def update_pan(self):
        """Пока мышь принадлежит PAN, сдвиг мимо порога = перетаскивание камеры.
        Если кнопку отпустили без сдвига, возвращает позицию отложенного ПКМ-клика (иначе None)."""
        st = self._pan
        if st is None:
            return None
        if self.input.mouse_owner != MouseOwner.PAN:             # кнопку отпустили
            self._pan = None
            if not st["dragged"] and self.free_camera:
                return st["start"]
            return None

        mx, my = self.input.mouse_pos
        if not st["dragged"]:
            sx, sy = st["start"]
            if math.hypot(mx - sx, my - sy) < PAN_DRAG_THRESHOLD_PX:
                return None
            st["dragged"] = True
        lx, ly = st["last"]
        z = self.camera.zoom
        self.camera.move_by(-(mx - lx) / z, -(my - ly) / z)      # мир следует за курсором
        st["last"] = (mx, my)
        return None