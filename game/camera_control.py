"""game/camera_control.py — зум, размер окна, свободная камера и следование за танком."""
import math

from inputs import Action, MouseOwner

PAN_DRAG_THRESHOLD_PX = 5     # на сколько px надо сдвинуть мышь с зажатой ПКМ, чтобы это считалось перетаскиванием

class CameraController:
    def __init__(self, camera, input_handler):
        self.camera = camera
        self.input = input_handler
        self.free_camera = False         # свободная камера (L): не следует за танком
        self._pan = None                 # при нажатой ПКМ: {"start", "last", "dragged"}

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

    def follow(self, tank):
        if not self.free_camera:
            self.camera.center_on(tank.x, tank.y)

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