"""combat/projectile.py — снаряд: полёт, попадание, рикошет, отрисовка."""
import random

import pygame

from engine import heading_vector
from .armor import is_ricochet

SHELL_COLOR = (205, 160, 105)       # светло-коричневый
SHELL_LIGHT = (234, 202, 154)       # блик по центру
SHELL_TIP = (150, 108, 64)          # наконечник темнее

RICOCHET_LOSS = (0.30, 0.35)         # сколько силы теряет снаряд при рикошете (случайно в этих пределах)
RICOCHET_RANGE_K = 0.5               # во сколько раз сокращается оставшаяся дальность
RICOCHET_MAX = 3                     # максимум рикошетов у одного снаряда
RICOCHET_PUSH_PX = 1.5               # на сколько px выталкиваем снаряд от стены (иначе он «застрянет» в грани)

# ==========================================
# СНАРЯД
# ==========================================

class Shell:
    def __init__(self, x, y, heading_deg, spec, origin=None, owner=None):
        self.x, self.y = x, y
        self._sx, self._sy = origin if origin is not None else (x, y)   # откуда считаем отрезок пролёта
        self.dx, self.dy = heading_vector(heading_deg)
        self.speed = spec.SHELL_SPEED_PX
        self.length = spec.SHELL_LEN_PX
        self.thick = spec.SHELL_THICK_PX
        self.range_left = spec.SHELL_RANGE_PX
        self.spec = spec                  # параметры взрыва берём из той же спецификации, что и выстрел
        self.alive = True
        self.exploded = False
        self.owner = owner                # кто стрелял: в него снаряд не попадает
        self.hit_target = None            # цель, в которую попали (стена, танк...)
        self.hit_normal = None            # нормаль грани, в которую попали (нужна танку для выбора брони)
        self.hit_cos = 1.0                # косинус угла между траекторией и нормалью грани (1 = прямой удар)
        self.power = 1.0                  # доля силы: 1.0 в начале, после каждого рикошета уменьшается
        self.bounces = 0                  # сколько раз уже отскочил
        self.ricochet_at = None           # (x, y), если рикошет случился в этом кадре (читает EffectsSystem)

    def update(self, dt, targets=None):
        step = min(self.speed * dt, self.range_left)
        nx = self.x + self.dx * step
        ny = self.y + self.dy * step

        if targets is not None:
            hit = targets.raycast(self._sx, self._sy, nx, ny, ignore=self.owner)
            if hit is not None:
                target, t, normal = hit
                hx = self._sx + (nx - self._sx) * t           # точка попадания на грани
                hy = self._sy + (ny - self._sy) * t

                if normal is not None:
                    cos_i = abs(self.dx * normal[0] + self.dy * normal[1])
                    if self.bounces < RICOCHET_MAX and is_ricochet(cos_i):
                        self._ricochet(hx, hy, normal)
                        return
                    self.hit_cos = cos_i

                self.x, self.y = hx, hy
                self.hit_target = target
                self.hit_normal = normal
                self.alive = False
                self.exploded = True
                return

        self.x, self.y = nx, ny
        self._sx, self._sy = nx, ny
        self.range_left -= step
        if self.range_left <= 0.0:
            self.alive = False
            self.exploded = True

    def _ricochet(self, hx, hy, normal):
        """Зеркальный отскок: отражаем направление, режем силу и оставшуюся дальность."""
        # сколько уже пролетел до точки удара (на первом кадре точка может быть позади дульного среза)
        travelled = max(0.0, (hx - self.x) * self.dx + (hy - self.y) * self.dy)
        self.range_left = (self.range_left - travelled) * RICOCHET_RANGE_K

        dot = self.dx * normal[0] + self.dy * normal[1]       # < 0: нормаль смотрит против движения
        self.dx -= 2.0 * dot * normal[0]
        self.dy -= 2.0 * dot * normal[1]

        self.power *= 1.0 - random.uniform(*RICOCHET_LOSS)
        self.bounces += 1

        # ставим снаряд чуть снаружи грани и начинаем отсчёт отрезка пролёта заново отсюда
        self.x = hx + normal[0] * RICOCHET_PUSH_PX
        self.y = hy + normal[1] * RICOCHET_PUSH_PX
        self._sx, self._sy = self.x, self.y
        self.ricochet_at = (hx, hy)

        if self.range_left <= 0.0:
            self.alive = False
            self.exploded = True

    def draw(self, screen, camera):
        z = camera.zoom
        hx, hy = camera.world_to_screen(self.x, self.y)
        length = self.length * z
        tx, ty = hx - self.dx * length, hy - self.dy * length
        thick = max(2, int(round(self.thick * z)))
        pygame.draw.line(screen, SHELL_COLOR, (tx, ty), (hx, hy), thick)
        pygame.draw.line(screen, SHELL_LIGHT, (tx, ty), (hx, hy), max(1, thick // 3))
        nx, ny = hx - self.dx * length * 0.2, hy - self.dy * length * 0.2
        pygame.draw.line(screen, SHELL_TIP, (nx, ny), (hx, hy), thick)