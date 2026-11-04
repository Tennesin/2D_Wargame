"""game/match/control/camera.py — зум, размер окна, свободная камера и следование за танком."""
import math
import random
from inputs import Action, MouseOwner
from .look_ahead import LookAhead

PAN_DRAG_THRESHOLD_PX = 5     # на сколько px надо сдвинуть мышь с зажатой ПКМ, чтобы это считалось перетаскиванием
SHAKE_DECAY_S = 0.35          # за сколько секунд тряска стихает от максимума
SHAKE_MAX_PX = 14.0           # размах при максимальной силе, экранные px

class CameraController:
    def __init__(self, camera, input_handler):
        self.camera = camera
        self.input = input_handler
        self.free_camera = False         # свободная камера (L): не следует за танком
        self._pan = None                 # при нажатой ПКМ: {"start", "last", "dragged"}
        self._look = LookAhead()         # плавное смещение обзора к курсору
        self._shake = 0.0                # текущая сила тряски 0..1
        self._shake_xy = (0.0, 0.0)      # смещение этого кадра (follow зовут дважды: берём одно и то же)

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
        """Зум (колёсико и зажатые клавиши, плавно) и размер окна."""
        self.camera.zoom_hold(self.input.zoom_key_direction(), dt)
        steps = self.input.pop_zoom_steps()
        if steps:
            self.camera.zoom_wheel(steps)
        self.camera.update_zoom(dt)
        self.camera.resize(*size)

    def follow(self, tank, dt=0.0):
        """Центр камеры = корпус танка + сглаженное смещение в сторону курсора."""
        if self.free_camera:
            return
        hx, hy = tank.hull_obb()[:2]
        ox, oy = self._look.offset(dt, self.camera, self.input)
        sx, sy = self._shake_offset(dt)
        z = self.camera.zoom
        self.camera.center_on(hx + ox + sx / z, hy + oy + sy / z)

    def add_shake(self, amount):
        """Толчок камеры: amount 0..1. Не складывается, берётся сильнейший."""
        self._shake = min(1.0, max(self._shake, amount))

    def _shake_offset(self, dt):
        if dt > 0.0:
            self._shake = max(0.0, self._shake - dt / SHAKE_DECAY_S)
            amp = SHAKE_MAX_PX * self._shake * self._shake
            self._shake_xy = (random.uniform(-amp, amp), random.uniform(-amp, amp))
        return self._shake_xy

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