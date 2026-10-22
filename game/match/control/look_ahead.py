"""game/match/control/look_ahead.py — плавное смещение обзора в сторону курсора."""
import math

from ...config import LOOK_AHEAD, LOOK_MARGIN_PX

LOOK_DEADZONE = 0.25          # доля полуразмера экрана вокруг центра, где цель смещения равна нулю
LOOK_ACCEL = 1.0              # разгон и торможение камеры, доли экрана в секунду за секунду
LOOK_VMAX = 0.4               # потолок скорости камеры, доли экрана в секунду

def _dead(n, zone):
    """Нормированное отклонение n (-1..1) с вырезанной мёртвой зоной; результат снова -1..1."""
    a = abs(n)
    if a <= zone:
        return 0.0
    return math.copysign(min(1.0, (a - zone) / (1.0 - zone)), n)

class LookAhead:
    """Сглаженное смещение камеры от корпуса к курсору. Работает в долях экрана,
    поэтому смена зума и размера окна рывка не даёт."""

    def __init__(self):
        self._target = [0.0, 0.0]        # куда тянется обзор: доли экрана -1..1 (по X и Y)
        self._look = [0.0, 0.0]          # текущее сглаженное смещение, те же доли
        self._vel = [0.0, 0.0]           # скорость смещения, доли экрана в секунду

    def offset(self, dt, camera, input_handler):
        """Смещение камеры от корпуса, мировые px."""
        self._update_target(camera, input_handler)
        if dt > 0.0:
            for i in (0, 1):
                self._step_axis(i, dt)
        z = camera.zoom
        max_x = max(0.0, (camera.view_w / 2.0 - LOOK_MARGIN_PX) / z)
        max_y = max(0.0, (camera.view_h / 2.0 - LOOK_MARGIN_PX) / z)
        return self._look[0] * max_x, self._look[1] * max_y

    def _update_target(self, camera, input_handler):
        """Цель берётся из положения мыши. Если курсор не работает на мир (над интерфейсом,
        вращение стены) или вне окна, прежняя цель сохраняется."""
        if not LOOK_AHEAD:
            self._target[0] = self._target[1] = 0.0
            return
        if not input_handler.pointer_in_world or not input_handler.mouse_focused:
            return
        half_w, half_h = camera.view_w / 2.0, camera.view_h / 2.0
        if half_w <= 0 or half_h <= 0:
            return
        mx, my = input_handler.mouse_pos
        self._target[0] = _dead((mx - half_w) / half_w, LOOK_DEADZONE)
        self._target[1] = _dead((my - half_h) / half_h, LOOK_DEADZONE)

    def _step_axis(self, i, dt):
        """Один шаг разгона/торможения по оси i."""
        diff = self._target[i] - self._look[i]
        vel = self._vel[i]

        if abs(diff) < 1e-4 and abs(vel) < 1e-3:
            self._look[i] = self._target[i]
            self._vel[i] = 0.0
            return

        allowed = min(LOOK_VMAX, math.sqrt(2.0 * LOOK_ACCEL * abs(diff)))
        want = math.copysign(allowed, diff)

        dv = want - vel
        max_dv = LOOK_ACCEL * dt
        if abs(dv) > max_dv:
            dv = math.copysign(max_dv, dv)
        vel += dv

        move = vel * dt
        if diff * (diff - move) <= 0.0:
            self._look[i] = self._target[i]
            self._vel[i] = 0.0
            return

        self._look[i] += move
        self._vel[i] = vel