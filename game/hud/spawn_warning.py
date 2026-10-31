"""game/hud/spawn_warning.py — мигающий синий треугольник у рамки экрана: где появится группа врагов."""
import math

from .colors import FILL, OUTLINE
from .pointers import edge_point, draw_triangle, avoid_interface

WARN_SIZE = 34           # крупнее маркеров ботов (13 px)
WARN_INSET = 56          # отступ от края экрана, px

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
        nx, ny = avoid_interface(w, h, px, py, WARN_SIZE, WARN_INSET)
        if (nx, ny) != (px, py):
            px, py = nx, ny
            ang = math.atan2(sy - py, sx - px)       # остриё по-прежнему смотрит на точку появления
        draw_triangle(screen, px, py, ang, WARN_SIZE, FILL, OUTLINE, width=3)