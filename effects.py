"""effects.py — снаряды, вспышка выстрела, дым, взрыв снаряда и тёмные пятна на земле.
Все размеры здесь в МИРОВЫХ пикселях (100 px = 1 м); на экран переводятся через camera.zoom."""
import math
import random

import pygame
from armor import is_ricochet

SHELL_COLOR = (205, 160, 105)       # светло-коричневый
SHELL_LIGHT = (234, 202, 154)       # блик по центру
SHELL_TIP = (150, 108, 64)          # наконечник темнее

RICOCHET_LOSS = (0.30, 0.35)         # сколько силы теряет снаряд при рикошете (случайно в этих пределах)
RICOCHET_RANGE_K = 0.5               # во сколько раз сокращается оставшаяся дальность
RICOCHET_MAX = 3                     # максимум рикошетов у одного снаряда
RICOCHET_PUSH_PX = 1.5               # на сколько px выталкиваем снаряд от стены (иначе он «застрянет» в грани)

FLASH_LAYERS = (                     # (масштаб, цвет): от внешнего слоя к внутреннему
    (1.00, (255, 140, 40)),
    (0.70, (255, 205, 70)),
    (0.40, (255, 248, 215)),
)

BLAST_LAYERS = (                     # огненный шар взрыва: от внешнего слоя к ядру
    (1.00, (190, 75, 30)),
    (0.72, (255, 140, 40)),
    (0.46, (255, 210, 90)),
    (0.22, (255, 245, 210)),
)
DIRT_COLORS = ((92, 70, 48), (72, 54, 38), (110, 88, 60))

SCORCH_COLOR = (18, 14, 10)
SCORCH_MAX_ALPHA = 150

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
    def __init__(self, x, y, heading_deg, spec, origin=None, owner=None):
        self.x, self.y = x, y
        self._sx, self._sy = origin if origin is not None else (x, y)   # откуда считаем отрезок пролёта
        self.dx, self.dy = _dir(heading_deg)
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
        self.hit_wall = None              # стена, в которую попали (если попали)
        self.hit_cos = 1.0                # косинус угла между траекторией и нормалью грани (1 = прямой удар)
        self.power = 1.0                  # доля силы: 1.0 в начале, после каждого рикошета уменьшается
        self.bounces = 0                  # сколько раз уже отскочил
        self.ricochet_at = None           # (x, y), если рикошет случился в этом кадре (читает EffectsSystem)

    def update(self, dt, camera, targets=None):
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


# ==========================================
# ВСПЫШКА ВЫСТРЕЛА
# ==========================================
class MuzzleFlash:
    def __init__(self, x, y, heading_deg, spec, anchor=None):
        self.x, self.y = x, y
        self.dx, self.dy = _dir(heading_deg)
        self.px, self.py = -self.dy, self.dx            # перпендикуляр (вправо от ствола)
        self.size = spec.FLASH_SIZE_PX
        self.life = spec.FLASH_TIME
        self.age = 0.0
        self.anchor = anchor

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        if self.anchor is not None:
            self.x, self.y = self.anchor.muzzle_point()
            self.dx, self.dy = _dir(self.anchor.turret_angle)
            self.px, self.py = -self.dy, self.dx
        self.age += dt

    def _to_screen(self, camera, u, v):
        """u — вперёд по стволу, v — вбок (мировые px); результат — экранные координаты."""
        z = camera.zoom
        ox, oy = camera.world_to_screen(self.x, self.y)
        return (ox + (self.dx * u + self.px * v) * z,
                oy + (self.dy * u + self.py * v) * z)

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
        pygame.draw.circle(screen, (255, 235, 170), center, max(2, int(L * 0.22 * camera.zoom)))


# ==========================================
# ДЫМ: кривые серые полоски
# ==========================================
class SmokeStreak:
    def __init__(self, x, y, heading_deg, spec, rng, anchor=None):
        self.anchor = anchor                              # танк, к стволу которого привязан дым (или None)
        self.rel = rng.uniform(-60, 60)                   # угол полоски относительно ствола (веер вперёд)
        self._set_pose(x, y, heading_deg)

        self.dist = spec.SMOKE_REACH_PX * rng.uniform(0.55, 1.0)      # куда доползает
        self.life = spec.SMOKE_TIME * rng.uniform(0.9, 1.0)
        self.width = spec.SMOKE_WIDTH_PX
        self.amp = self.dist * rng.uniform(0.08, 0.20) * rng.choice((-1, 1))   # размах «кривизны»
        self.freq = 2.0 * math.pi / (self.dist * rng.uniform(0.5, 0.9))
        self.phase = rng.uniform(0.0, 2.0 * math.pi)
        self.vx = rng.uniform(-32.0, 32.0)                # лёгкий снос ветром (px мира в секунду)
        self.vy = rng.uniform(-56.0, -8.0)
        self.shade = rng.randint(135, 185)                # у каждой полоски свой оттенок серого
        self.age = 0.0

    def _set_pose(self, x, y, heading_deg):
        """Начало полоски и направление веера (по текущему положению ствола)."""
        self.x, self.y = x, y
        self.dx, self.dy = _dir(heading_deg + self.rel)
        self.px, self.py = -self.dy, self.dx

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        if self.anchor is not None:
            self._set_pose(*self.anchor.muzzle_point(), self.anchor.turret_angle)
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
        width = max(1, int(round(self.width * (1.0 - 0.5 * u) * camera.zoom)))
        c = self.shade
        pygame.draw.lines(overlay, (c, c, c, alpha), False, pts, width)


# ==========================================
# ВЗРЫВ СНАРЯДА: огненный шар + комья земли
# ==========================================
class Explosion:
    def __init__(self, x, y, spec, rng):
        self.x, self.y = x, y
        self.size = spec.BLAST_SIZE_PX
        self.life = spec.BLAST_TIME
        self.age = 0.0
        self.dirt = []                    # (dx, dy, на сколько разлетится, размер комка, цвет)
        for _ in range(spec.BLAST_DIRT_COUNT):
            ang = rng.uniform(0.0, 2.0 * math.pi)
            self.dirt.append((math.cos(ang), math.sin(ang),
                              self.size * rng.uniform(0.9, 2.0),
                              self.size * rng.uniform(0.07, 0.16),
                              rng.choice(DIRT_COLORS)))

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        self.age += dt

    def draw(self, screen, camera):
        z = camera.zoom
        u = self.age / self.life                           # 0 -> 1
        cx, cy = camera.world_to_screen(self.x, self.y)

        # огненный шар: быстро растёт (первые 40%), потом сжимается и гаснет
        grow = 1.0 - (1.0 - min(1.0, u / 0.4)) ** 2
        fade = max(0.0, (u - 0.4) / 0.6)
        for scale, color in BLAST_LAYERS:
            r = self.size * 0.5 * scale * grow * (1.0 - fade) * z
            if r >= 1.0:
                pygame.draw.circle(screen, color, (round(cx), round(cy)), int(r))

        # комья земли разлетаются и уменьшаются
        for dxn, dyn, dist, sz, color in self.dirt:
            d = dist * (1.0 - (1.0 - u) ** 2)
            pos = (round(cx + dxn * d * z), round(cy + dyn * d * z))
            pygame.draw.circle(screen, color, pos, max(1, round(sz * (1.0 - 0.6 * u) * z)))


# ==========================================
# ТЁМНОЕ ПЯТНО НА ЗЕМЛЕ
# ==========================================
class Scorch:
    def __init__(self, x, y, spec, rng):
        self.x, self.y = x, y
        self.life = spec.SCORCH_TIME
        self.age = 0.0
        r = spec.SCORCH_RADIUS_PX
        self.lumps = []                   # неровное пятно из нескольких кругов: (смещение x, y, радиус)
        for _ in range(7):
            ang = rng.uniform(0.0, 2.0 * math.pi)
            off = r * rng.uniform(0.0, 0.45)
            self.lumps.append((math.cos(ang) * off, math.sin(ang) * off, r * rng.uniform(0.45, 0.75)))

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        self.age += dt

    def draw(self, overlay, camera):
        z = camera.zoom
        u = self.age / self.life
        cx, cy = camera.world_to_screen(self.x, self.y)
        # быстро проявляется (0.05 с), затем плавно тает
        alpha = SCORCH_MAX_ALPHA * min(1.0, self.age / 0.05) * (1.0 - u) ** 1.3
        # три слоя: внешний бледный, внутренний тёмный (на слое рисунок заменяет пиксели, а не смешивается)
        for scale, k in ((1.0, 0.35), (0.72, 0.65), (0.45, 1.0)):
            color = (*SCORCH_COLOR, int(alpha * k))
            for ox, oy, r in self.lumps:
                pr = int(round(r * scale * z))
                if pr >= 1:
                    pygame.draw.circle(overlay, color, (round(cx + ox * z), round(cy + oy * z)), pr)

# ==========================================
# ИСКРЫ РИКОШЕТА
# ==========================================
class Spark:
    def __init__(self, x, y, dx, dy, rng):
        self.x, self.y = x, y
        self.life = 0.18
        self.age = 0.0
        base = math.atan2(dy, dx)                         # искры летят в сторону отскока веером
        self.rays = []
        for _ in range(7):
            ang = base + rng.uniform(-0.7, 0.7)
            self.rays.append((math.cos(ang), math.sin(ang), rng.uniform(40.0, 110.0)))

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt, camera):
        self.age += dt

    def draw(self, screen, camera):
        z = camera.zoom
        u = self.age / self.life
        cx, cy = camera.world_to_screen(self.x, self.y)
        for ux, uy, ln in self.rays:
            head = ln * (0.4 + 0.6 * u)
            tail = ln * 0.8 * u
            pygame.draw.line(screen, (255, 225, 140),
                             (cx + ux * tail * z, cy + uy * tail * z),
                             (cx + ux * head * z, cy + uy * head * z), 2)

# ==========================================
# МЕНЕДЖЕР ЭФФЕКТОВ
# ==========================================
class EffectsSystem:
    def __init__(self):
        self.shells = []
        self.flashes = []
        self.smoke = []
        self.explosions = []
        self.scorches = []
        self.sparks = []
        self._layers = {}                 # прозрачные слои во весь экран (для полупрозрачности)
        self._rng = random.Random()

    def spawn_shot(self, shot, spec, tank=None):
        dx, dy = _dir(shot.angle)
        origin = (shot.x - dx * spec.MUZZLE_DIST_PX,        # центр танка: оттуда считаем первый отрезок пролёта
                  shot.y - dy * spec.MUZZLE_DIST_PX)
        self.shells.append(Shell(shot.x, shot.y, shot.angle, spec, origin, owner=tank))
        self.flashes.append(MuzzleFlash(shot.x, shot.y, shot.angle, spec))
        for _ in range(spec.SMOKE_STREAKS):
            self.smoke.append(SmokeStreak(shot.x, shot.y, shot.angle, spec, self._rng, anchor=tank))

    def _spawn_impact(self, shell):
        self.explosions.append(Explosion(shell.x, shell.y, shell.spec, self._rng))
        self.scorches.append(Scorch(shell.x, shell.y, shell.spec, self._rng))

    def update(self, dt, camera, targets=None):
        """Возвращает попадания [(цель, spec, cos_impact, normal, power), ...]:
        урон применяет Game, а не эффекты."""
        for shell in self.shells:
            shell.update(dt, camera, targets)
        for group in (self.flashes, self.smoke, self.explosions, self.scorches, self.sparks):
            for obj in group:
                obj.update(dt, camera)

        hits = []
        for shell in self.shells:
            if shell.ricochet_at is not None:             # отскок: только искры, без взрыва
                self.sparks.append(Spark(*shell.ricochet_at, shell.dx, shell.dy, self._rng))
                shell.ricochet_at = None
            if shell.exploded:
                self._spawn_impact(shell)
                if shell.hit_target is not None:
                    hits.append((shell.hit_target, shell.spec, shell.hit_cos,
                                 shell.hit_normal, shell.power))

        self.shells = [o for o in self.shells if o.alive]
        self.flashes = [o for o in self.flashes if o.alive]
        self.smoke = [o for o in self.smoke if o.alive]
        self.explosions = [o for o in self.explosions if o.alive]
        self.scorches = [o for o in self.scorches if o.alive]
        self.sparks = [o for o in self.sparks if o.alive]
        return hits

    def _layer(self, name, size):
        """Очищенный прозрачный слой (пересоздаётся только при смене размера окна)."""
        layer = self._layers.get(name)
        if layer is None or layer.get_size() != size:
            layer = pygame.Surface(size, pygame.SRCALPHA)
            self._layers[name] = layer
        layer.fill((0, 0, 0, 0))
        return layer

    def draw_ground(self, screen, camera):
        """Всё, что лежит на земле (рисуется ДО танка, чтобы пятна были под ним)."""
        if self.scorches:
            layer = self._layer("scorch", screen.get_size())
            for s in self.scorches:
                s.draw(layer, camera)
            screen.blit(layer, (0, 0))

    def draw(self, screen, camera):
        """Всё, что летит и горит (рисуется ПОСЛЕ танка)."""
        if self.smoke:
            layer = self._layer("smoke", screen.get_size())
            for s in self.smoke:
                s.draw(layer, camera)
            screen.blit(layer, (0, 0))
        for shell in self.shells:
            shell.draw(screen, camera)
        for boom in self.explosions:
            boom.draw(screen, camera)
        for flash in self.flashes:
            flash.draw(screen, camera)
        for spark in self.sparks:
            spark.draw(screen, camera)