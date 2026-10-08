"""world/camera.py — камера: центр в мировых координатах и зум."""
from engine import clamp

ZOOM_LEVELS = [round(0.10 * 6 ** (i / 20), 4) for i in range(21)]   # 0.10 … 0.60, шаг ≈ 9 %
DEFAULT_ZOOM_LEVEL = 5                                              # ≈ 0.157: танк 7 м ≈ 110 px

# ==========================================
# КАМЕРА
# ==========================================

class Camera:
    """Камера: центр в мировых координатах + зум. Мир: 100 px = 1 м; на экране 1 м = 100 * zoom px.
    Меняй положение только через center_on / move_by / zoom_by / resize: они обновляют кэш."""

    def __init__(self, view_w=800, view_h=600):
        self.x = 0.0
        self.y = 0.0
        self.view_w = view_w
        self.view_h = view_h
        self.zoom_level = DEFAULT_ZOOM_LEVEL
        self._z = 1.0
        self._left = 0
        self._top = 0
        self._refresh()

    def _refresh(self):
        """Пересчитать зум и сдвиг мира в экранных пикселях (целые числа, чтобы земля не дрожала)."""
        z = ZOOM_LEVELS[self.zoom_level]
        self._z = z
        self._left = round(self.x * z) - self.view_w // 2
        self._top = round(self.y * z) - self.view_h // 2

    @property
    def zoom(self):
        return self._z

    def zoom_by(self, steps):
        """Сдвинуть уровень зума: steps > 0 — приблизить, < 0 — отдалить."""
        self.zoom_level = int(clamp(self.zoom_level + steps, 0, len(ZOOM_LEVELS) - 1))
        self._refresh()

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