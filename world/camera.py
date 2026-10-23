"""world/camera.py — камера: центр в мировых координатах и зум (плавный в партии, ступенчатый для превью)."""
import math

from engine import clamp, WORLD

ZOOM_LEVELS = [round(0.10 * 6 ** (i / 20), 4) for i in range(21)]
DEFAULT_ZOOM_LEVEL = 7

# --- плавный зум в партии ---
ZOOM_MIN = ZOOM_LEVELS[0]              # самый далёкий вид
ZOOM_MAX = 0.30                        # ближе в партии не приближаем (обзор важнее)
ZOOM_WHEEL_STEP = 6 ** (1 / 20)        # один щелчок колёсика = одна прежняя ступень
ZOOM_HOLD_RATE = 1.0                   # скорость при зажатой клавише (натуральный логарифм зума в секунду)
ZOOM_SMOOTH = 10.0                     # чем больше, тем резвее зум догоняет цель (1/с)
ZOOM_SNAP = 0.002                      # ближе к цели, чем это (в логарифме): считаем, что дошли

# ==========================================
# КАМЕРА
# ==========================================

class Camera:
    """Камера: центр в мировых координатах + зум. Мир: 100 px = 1 м; на экране 1 м = 100 * zoom px.
    Меняй положение только через center_on / move_by / resize и методы зума: они обновляют кэш.
    Партия двигает зум через zoom_wheel / zoom_hold / update_zoom (плавно),
    а превью конструктора и иконки через zoom_by (мгновенные ступени)."""

    def __init__(self, view_w=800, view_h=600):
        self.x = 0.0
        self.y = 0.0
        self.view_w = view_w
        self.view_h = view_h
        self.zoom_level = DEFAULT_ZOOM_LEVEL      # нужен только ступенчатому zoom_by
        self._z = ZOOM_LEVELS[DEFAULT_ZOOM_LEVEL]
        self._target = self._z                    # куда зум плавно подтягивается
        self._left = 0
        self._top = 0
        self._refresh()

    def _refresh(self):
        """Пересчитать сдвиг мира в экранных пикселях (целые числа, чтобы земля не дрожала)."""
        self.x = clamp(self.x, -WORLD.cam_w_px, WORLD.cam_w_px)
        self.y = clamp(self.y, -WORLD.cam_h_px, WORLD.cam_h_px)
        z = self._z
        self._left = round(self.x * z) - self.view_w // 2
        self._top = round(self.y * z) - self.view_h // 2

    @property
    def zoom(self):
        return self._z

    @property
    def is_zooming(self):
        """Зум ещё не дошёл до цели (идёт плавное приближение или отдаление)."""
        return self._z != self._target

    # ---------- ступенчатый зум (конструктор, иконки) ----------
    def zoom_by(self, steps):
        """Мгновенно сдвинуть уровень зума: steps > 0 приблизить, < 0 отдалить."""
        self.zoom_level = int(clamp(self.zoom_level + steps, 0, len(ZOOM_LEVELS) - 1))
        self._z = self._target = ZOOM_LEVELS[self.zoom_level]
        self._refresh()

    # ---------- плавный зум (партия) ----------
    def zoom_wheel(self, steps):
        """Колёсико: сдвигает ЦЕЛЬ зума на steps ступеней (steps > 0 приблизить)."""
        self._target = clamp(self._target * ZOOM_WHEEL_STEP ** steps, ZOOM_MIN, ZOOM_MAX)

    def zoom_hold(self, direction, dt):
        """Клавиша зажата: цель непрерывно ползёт. direction: +1 приближать, -1 отдалять, 0 ничего."""
        if direction == 0 or dt <= 0.0:
            return
        self._target = clamp(self._target * math.exp(direction * ZOOM_HOLD_RATE * dt),
                             ZOOM_MIN, ZOOM_MAX)

    def update_zoom(self, dt):
        """Каждый кадр: зум плавно догоняет цель."""
        if self._z == self._target:
            return
        diff = math.log(self._target / self._z)
        if abs(diff) < ZOOM_SNAP:
            self._z = self._target
        else:
            self._z *= math.exp(diff * (1.0 - math.exp(-ZOOM_SMOOTH * dt)))
        self._refresh()

    # ---------- остальное ----------
    def resize(self, view_w, view_h):
        self.view_w = view_w
        self.view_h = view_h
        self._refresh()

    def center_on(self, x, y):
        self.x = x
        self.y = y
        self._refresh()

    def move_by(self, dx, dy):
        """Сдвинуть камеру на (dx, dy) мировых px (свободная камера)."""
        self.x += dx
        self.y += dy
        self._refresh()

    def origin_px(self):
        """Сдвиг мира в ЭКРАННЫХ пикселях."""
        return self._left, self._top

    def world_to_screen(self, wx, wy):
        z = self._z
        return wx * z - self._left, wy * z - self._top

    def screen_to_world(self, sx, sy):
        z = self._z
        return (sx + self._left) / z, (sy + self._top) / z