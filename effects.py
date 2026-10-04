"""effects.py — снаряды, вспышка выстрела и дым пороховых газов."""
import math
import random

import pygame

SHELL_COLOR = (205, 160, 105)       # светло-коричневый
SHELL_LIGHT = (234, 202, 154)       # блик по центру
SHELL_TIP = (150, 108, 64)          # наконечник темнее

FLASH_LAYERS = (                     # (масштаб, цвет): от внешнего слоя к внутреннему
    (1.00, (255, 140, 40)),
    (0.70, (255, 205, 70)),
    (0.40, (255, 248, 215)),
)

SMOKE_MAX_ALPHA = 190
SMOKE_POINTS = 12                    # из скольких отрезков состоит одна полоска


def _dir(heading_deg):
    """Угол (0 = вверх, по часовой) -> единичный вектор на экране/в мире."""
    rad = math.radians(heading_deg)
    return math.sin(rad), -math.cos(rad)


# ==========================================
# СНАРЯД
# ==========================================
class Shell:
    def __init__(self, x, y, heading_deg, spec):
        self.x, self.y = x, y
        self.dx, self.dy = _dir(heading_deg)
        self.speed = spec.SHELL_SPEED_PX
        self.length = spec.SHELL_LEN_PX
        self.thick = max(2, int(round(spec.SHELL_THICK_PX)))
        self.alive = True

    def update(self, dt, camera):
        self.x += self.dx * self.speed * dt
        self.y += self.dy * self.speed * dt
        # удаляем, когда и голова, и хвост снаряда уже за экраном
        sx, sy = camera.world_to_screen(self.x, self.y)
        m = self.length + 20
        if not (-m <= sx <= camera.view_w + m and -m <= sy <= camera.view_h + m):
            self.alive = False

    def draw(self, screen, camera):
        hx, hy = camera.world_to_screen(self.x, self.y)
        tx, ty = hx - self.dx * self.length, hy - self.dy * self.length
        pygame.draw.line(screen, SHELL_COLOR, (tx, ty), (hx, hy), self.thick)
        pygame.draw.line(screen, SHELL_LIGHT, (tx, ty), (hx, hy), max(1, self.thick // 3))
        nx, ny = hx - self.dx * self.length * 0.2, hy - self.dy * self.length * 0.2
        pygame.draw.line(screen, SHELL_TIP, (nx, ny), (hx, hy), self.thick)


# ==========================================
# ВСПЫШКА ВЫСТРЕЛА
# ==========================================
class MuzzleFlash:
    def __init__(self, x, y, heading_deg, spec):
        self.x, self.y = x, y
        self.dx, self.dy = _dir(heading_deg)
        self.px, self.py = -self.dy, self.dx            # перпендикуляр (вправо от ствола)
        self.size = spec.FLASH_SIZE_PX
        self.life = spec.FLASH_TIME
        self.age = 0.0

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        self.age += dt

    def _to_screen(self, camera, u, v):
        """u — вперёд по стволу, v — вбок; результат — экранные координаты."""
        ox, oy = camera.world_to_screen(self.x, self.y)
        return (ox + self.dx * u + self.px * v,
                oy + self.dy * u + self.py * v)

    def draw(self, screen, camera):
        k = 1.0 - self.age / self.life                 # 1 -> 0
        L = self.size * (0.5 + 0.5 * k)                # вспышка съёживается

        # боковые «лепестки» (пороховые газы разлетаются в стороны)
        for side in (-1, 1):
            pts = [self._to_screen(camera, u, v) for u, v in
                   ((-L * 0.05, 0), (L * 0.18, side * L * 0.55), (L * 0.35, 0))]
            pygame.draw.polygon(screen, FLASH_LAYERS[0][1], pts)

        # основной язык пламени: три вложенных слоя
        for scale, color in FLASH_LAYERS:
            l = L * scale
            w = l * 0.5
            local = ((0, -w * 0.35), (l * 0.35, -w * 0.6), (l, 0),
                     (l * 0.35, w * 0.6), (0, w * 0.35))
            pygame.draw.polygon(screen, color, [self._to_screen(camera, u, v) for u, v in local])

        center = self._to_screen(camera, 0, 0)
        pygame.draw.circle(screen, (255, 235, 170), center, max(2, int(L * 0.22)))


# ==========================================
# ДЫМ: кривые серые полоски
# ==========================================
class SmokeStreak:
    def __init__(self, x, y, heading_deg, spec, rng):
        self.x, self.y = x, y
        self.dx, self.dy = _dir(heading_deg + rng.uniform(-60, 60))   # веер вперёд
        self.px, self.py = -self.dy, self.dx

        self.dist = spec.SMOKE_REACH_PX * rng.uniform(0.55, 1.0)      # куда доползает
        self.life = spec.SMOKE_TIME * rng.uniform(0.9, 1.0)
        self.width = spec.SMOKE_WIDTH_PX
        self.amp = self.dist * rng.uniform(0.08, 0.20) * rng.choice((-1, 1))   # размах «кривизны»
        self.freq = 2.0 * math.pi / (self.dist * rng.uniform(0.5, 0.9))
        self.phase = rng.uniform(0.0, 2.0 * math.pi)
        self.vx = rng.uniform(-8.0, 8.0)                  # лёгкий снос ветром
        self.vy = rng.uniform(-14.0, -2.0)
        self.shade = rng.randint(135, 185)                # у каждой полоски свой оттенок серого
        self.age = 0.0

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        self.age += dt

    def draw(self, overlay, camera):
        u = self.age / self.life
        head = self.dist * (1.0 - (1.0 - u) ** 2)         # голова: быстро вылетает, потом замедляется
        tu = max(0.0, (u - 0.25) / 0.75)
        tail = self.dist * tu ** 1.5                      # хвост догоняет голову, полоска исчезает
        if head - tail < 1.0:
            return

        pts = []
        for i in range(SMOKE_POINTS + 1):
            s = tail + (head - tail) * i / SMOKE_POINTS
            wob = math.sin(s * self.freq + self.phase + u * 2.0) * self.amp * (s / self.dist)
            wx = self.x + self.dx * s + self.px * wob + self.vx * self.age
            wy = self.y + self.dy * s + self.py * wob + self.vy * self.age
            pts.append(camera.world_to_screen(wx, wy))

        alpha = int(SMOKE_MAX_ALPHA * (1.0 - u) ** 1.2)
        width = max(1, int(round(self.width * (1.0 - 0.5 * u))))
        c = self.shade
        pygame.draw.lines(overlay, (c, c, c, alpha), False, pts, width)


# ==========================================
# МЕНЕДЖЕР ЭФФЕКТОВ
# ==========================================
class EffectsSystem:
    def __init__(self):
        self.shells = []
        self.flashes = []
        self.smoke = []
        self._overlay = None              # прозрачный слой для дыма (чтобы работала полупрозрачность)
        self._rng = random.Random()

    def spawn_shot(self, shot, spec):
        self.shells.append(Shell(shot.x, shot.y, shot.angle, spec))
        self.flashes.append(MuzzleFlash(shot.x, shot.y, shot.angle, spec))
        for _ in range(spec.SMOKE_STREAKS):
            self.smoke.append(SmokeStreak(shot.x, shot.y, shot.angle, spec, self._rng))

    def update(self, dt, camera):
        for group in (self.shells, self.flashes, self.smoke):
            for obj in group:
                obj.update(dt, camera)
        self.shells = [o for o in self.shells if o.alive]
        self.flashes = [o for o in self.flashes if o.alive]
        self.smoke = [o for o in self.smoke if o.alive]

    def draw(self, screen, camera):
        if self.smoke:
            size = screen.get_size()
            if self._overlay is None or self._overlay.get_size() != size:
                self._overlay = pygame.Surface(size, pygame.SRCALPHA)
            self._overlay.fill((0, 0, 0, 0))
            for s in self.smoke:
                s.draw(self._overlay, camera)
            screen.blit(self._overlay, (0, 0))
        for shell in self.shells:
            shell.draw(screen, camera)
        for flash in self.flashes:
            flash.draw(screen, camera)