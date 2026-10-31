"""game/hud/spawn_warning.py — мигающий синий треугольник у рамки экрана: где появится группа врагов."""
import math

from ui.hud import MARGIN as HUD_MARGIN, HEIGHT as HUD_HEIGHT, WIDTH as HUD_WIDTH
from ui.ammo_bar import OFFSET_X as AMMO_OFFSET_X, BTN as AMMO_BTN
from .colors import FILL, OUTLINE
from .pointers import edge_point, draw_triangle

WARN_SIZE = 34           # крупнее маркеров ботов (13 px)
WARN_INSET = 56          # отступ от края экрана, px

# Левый нижний интерфейс: сводка, столбик снарядов и строки подсказок над сводкой.
# Размер зоны подсказок задан с запасом: если добавишь больше строк, увеличь HUD_HINTS_H.
HUD_HINTS_W = 400        # ширина самой длинной строки подсказки, px
HUD_HINTS_H = 150        # высота стопки подсказок над сводкой, px
HUD_CLEARANCE = 12       # дополнительный зазор до интерфейса, px

def _hud_corner(screen_h):
    """Правая и верхняя границы занятой интерфейсом области в левом нижнем углу: (right, top)."""
    right = max(HUD_MARGIN + HUD_WIDTH + AMMO_OFFSET_X + AMMO_BTN, HUD_HINTS_W)
    top = screen_h - HUD_MARGIN - HUD_HEIGHT - HUD_HINTS_H
    return right, top

class SpawnWarning:
    def __init__(self, spawner, camera):
        self.spawner = spawner
        self.camera = camera

    def draw(self, screen):
        sp = self.spawner
        if not sp.warning_visible:
            return
        ax, ay = sp.anchor
        sx, sy = self.camera.world_to_screen(ax, ay)
        w, h = screen.get_size()
        px, py, ang = edge_point(w, h, sx, sy, WARN_INSET)
        nx, ny = self._avoid_hud(w, h, px, py)
        if (nx, ny) != (px, py):
            px, py = nx, ny
            ang = math.atan2(sy - py, sx - px)       # остриё по-прежнему смотрит на точку появления
        draw_triangle(screen, px, py, ang, WARN_SIZE, FILL, OUTLINE, width=3)

    @staticmethod
    def _avoid_hud(w, h, px, py):
        """Если точка попала в область интерфейса, сдвигает её вдоль стороны экрана, на которой она лежит."""
        right, top = _hud_corner(h)
        pad = WARN_SIZE + HUD_CLEARANCE
        if not (px < right + pad and py > top - pad):
            return px, py

        free_y = max(WARN_INSET, top - pad)                 # куда подняться вдоль левой стороны
        free_x = min(w - WARN_INSET, right + pad)           # куда уехать вдоль нижней стороны
        on_left = px <= WARN_INSET + 1.0
        on_bottom = py >= h - WARN_INSET - 1.0

        if on_left and on_bottom:                           # угол: идём туда, где короче
            if py - free_y <= free_x - px:
                return px, free_y
            return free_x, py
        if on_left:
            return px, free_y
        if on_bottom:
            return free_x, py
        return px, py