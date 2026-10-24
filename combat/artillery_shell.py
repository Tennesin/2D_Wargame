"""combat/artillery_shell.py — снаряд САУ: навесной полёт к точке на земле, тень и взрыв в конце.
Препятствия по пути не проверяются: снаряд летит по дуге над ними.
Позиция на земле движется строго по прямой, дуга существует только на экране (смещение вверх)."""
import math

import pygame

from engine import AMMO_COLORS, AmmoKind

ARC_HEIGHT_K = 0.10          # высота дуги в верхней точке = доля дистанции полёта
MIN_FLIGHT_S = 0.05          # страховка от нулевого времени полёта
SHELL_LEN_PER_MM = 1.0       # длина рисунка снаряда, px мира на мм калибра
SHELL_THICK_PER_MM = 0.10    # толщина рисунка снаряда
SHADOW_PER_MM = 0.35         # радиус тени, px мира на мм калибра
SHADOW_SQUASH = 0.6          # тень сплюснута по вертикали (эллипс)
SHADOW_SHRINK = 0.25         # на сколько тень сужается в верхней точке дуги
SHADOW_ALPHA = 90
BLAST_FIRE_K = 0.6           # огненный шар и пятно копоти считаются от этой доли внешнего радиуса

class ArtilleryShell:
    def __init__(self, x0, y0, tx, ty, spec, stats, owner=None):
        self.sx, self.sy = x0, y0              # дульный срез (мировые px)
        self.tx, self.ty = tx, ty              # точка падения (мировые px)
        self.spec = spec                       # орудие стрелка: из него берутся параметры эффектов взрыва
        self.stats = stats                     # ArtilleryStats
        self.owner = owner
        self.dist = math.hypot(tx - x0, ty - y0)
        self.flight_s = max(self.dist / stats.speed_px, MIN_FLIGHT_S)
        self.arc_px = self.dist * ARC_HEIGHT_K
        self.age = 0.0
        self.alive = True
        self.landed = False
        self._len = stats.caliber_mm * SHELL_LEN_PER_MM
        self._thick = stats.caliber_mm * SHELL_THICK_PER_MM
        self._shadow_r = stats.caliber_mm * SHADOW_PER_MM

    # ---------- состояние полёта ----------
    @property
    def target(self):
        return self.tx, self.ty

    @property
    def progress(self):
        """Доля пути 0..1."""
        return min(1.0, self.age / self.flight_s)

    @property
    def time_left(self):
        return max(0.0, self.flight_s - self.age)

    @property
    def ground_pos(self):
        """Где снаряд сейчас над землёй (по прямой от дульного среза к цели)."""
        u = self.progress
        return self.sx + (self.tx - self.sx) * u, self.sy + (self.ty - self.sy) * u

    def height_frac(self, u=None):
        """Высота над землёй в долях максимальной: 0 у земли, 1 в верхней точке дуги."""
        if u is None:
            u = self.progress
        return 4.0 * u * (1.0 - u)

    def update(self, dt):
        if not self.alive:
            return
        self.age += dt
        if self.age >= self.flight_s:
            self.age = self.flight_s
            self.alive = False
            self.landed = True

    # ---------- рисование снаряда ----------
    def draw(self, screen, camera):
        u = self.progress
        z = camera.zoom
        gx, gy = self.ground_pos
        sx, sy = camera.world_to_screen(gx, gy)
        hx, hy = sx, sy - self.arc_px * self.height_frac(u) * z     # дуга: смещение вверх по экрану

        # направление по касательной к экранной траектории (производная по u)
        dxdu = (self.tx - self.sx) * z
        dydu = (self.ty - self.sy) * z - 4.0 * self.arc_px * (1.0 - 2.0 * u) * z
        ln = math.hypot(dxdu, dydu)
        ux, uy = (dxdu / ln, dydu / ln) if ln > 1e-6 else (0.0, -1.0)

        length = max(6.0, self._len * z)
        thick = max(3, int(round(self._thick * z)))
        tx, ty = hx - ux * length, hy - uy * length
        body, light, tip = AMMO_COLORS[AmmoKind.HE]
        pygame.draw.line(screen, body, (tx, ty), (hx, hy), thick)
        pygame.draw.line(screen, light, (tx, ty), (hx, hy), max(1, thick // 3))
        nx, ny = hx - ux * length * 0.25, hy - uy * length * 0.25
        pygame.draw.line(screen, tip, (nx, ny), (hx, hy), thick)

    # ---------- тень на земле ----------
    def _shadow_radii(self, z):
        k = 1.0 - SHADOW_SHRINK * self.height_frac()
        rx = self._shadow_r * k * z
        return rx, rx * SHADOW_SQUASH

    def shadow_bounds(self, camera):
        """Рамка тени на экране (pygame.Rect)."""
        gx, gy = self.ground_pos
        sx, sy = camera.world_to_screen(gx, gy)
        rx, ry = self._shadow_radii(camera.zoom)
        return pygame.Rect(math.floor(sx - rx) - 1, math.floor(sy - ry) - 1,
                           math.ceil(2.0 * rx) + 3, math.ceil(2.0 * ry) + 3)

    def draw_shadow(self, overlay, camera, origin=(0, 0)):
        """origin — экранные координаты левого верхнего угла слоя overlay."""
        gx, gy = self.ground_pos
        sx, sy = camera.world_to_screen(gx, gy)
        rx, ry = self._shadow_radii(camera.zoom)
        rect = pygame.Rect(round(sx - rx - origin[0]), round(sy - ry - origin[1]),
                           max(2, round(2.0 * rx)), max(2, round(2.0 * ry)))
        pygame.draw.ellipse(overlay, (0, 0, 0, SHADOW_ALPHA), rect)