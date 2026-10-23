"""combat/effect_parts.py — визуальные части выстрела и попадания: вспышка, дым, взрыв,
след на земле, искры рикошета. Только рисуют и стареют: игровой логики здесь нет.
Все размеры в МИРОВЫХ пикселях (100 px = 1 м); на экран переводятся через camera.zoom."""
import math
import pygame

from engine import heading_vector

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

# ==========================================
# ВСПЫШКА ВЫСТРЕЛА
# ==========================================

class MuzzleFlash:
    def __init__(self, x, y, heading_deg, spec, anchor=None):
        self.x, self.y = x, y
        self.dx, self.dy = heading_vector(heading_deg)
        self.px, self.py = -self.dy, self.dx            # перпендикуляр (вправо от ствола)
        self.size = spec.FLASH_SIZE_PX
        self.life = spec.FLASH_TIME
        self.age = 0.0
        self.anchor = anchor

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        if self.anchor is not None:
            self.x, self.y = self.anchor.muzzle_point()
            self.dx, self.dy = heading_vector(self.anchor.turret_angle)
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
        self.dx, self.dy = heading_vector(heading_deg + self.rel)
        self.px, self.py = -self.dy, self.dx

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        if self.anchor is not None:
            self._set_pose(*self.anchor.muzzle_point(), self.anchor.turret_angle)
        self.age += dt

    def prepare(self, camera):
        """Точки, цвет и толщина полоски в экранных координатах; None, если рисовать нечего.
        Рисует полоски EffectsSystem: ему нужна общая рамка всех полосок."""
        u = self.age / self.life
        head = self.dist * (1.0 - (1.0 - u) ** 2)         # голова: быстро вылетает, потом замедляется
        tu = max(0.0, (u - 0.25) / 0.75)
        tail = self.dist * tu ** 1.5                      # хвост догоняет голову, полоска исчезает
        if head - tail < 1.0:
            return None

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
        return pts, (c, c, c, alpha), width

# ==========================================
# ВЗРЫВ СНАРЯДА: огненный шар + комья земли
# ==========================================

class Explosion:
    def __init__(self, x, y, spec, rng, radius_px=0.0):
        self.x, self.y = x, y
        self.size = spec.BLAST_SIZE_PX
        self.fire = max(self.size, radius_px * 1.6)    # диаметр огненного шара (у фугаса от радиуса взрыва)
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

    def update(self, dt):
        self.age += dt

    def draw(self, screen, camera):
        z = camera.zoom
        u = self.age / self.life                           # 0 -> 1
        cx, cy = camera.world_to_screen(self.x, self.y)

        # огненный шар: быстро растёт (первые 40%), потом сжимается и гаснет
        grow = 1.0 - (1.0 - min(1.0, u / 0.4)) ** 2
        fade = max(0.0, (u - 0.4) / 0.6)
        for scale, color in BLAST_LAYERS:
            r = self.fire * 0.5 * scale * grow * (1.0 - fade) * z
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
    def __init__(self, x, y, spec, rng, radius_px=0.0):
        self.x, self.y = x, y
        self.life = spec.SCORCH_TIME
        self.age = 0.0
        r = max(spec.SCORCH_RADIUS_PX, radius_px * 0.5)
        self.lumps = []                   # неровное пятно из нескольких кругов: (смещение x, y, радиус)
        self.reach = r * 1.25             # дальше этого радиуса от центра пятно не рисуется
        for _ in range(7):
            ang = rng.uniform(0.0, 2.0 * math.pi)
            off = r * rng.uniform(0.0, 0.45)
            self.lumps.append((math.cos(ang) * off, math.sin(ang) * off, r * rng.uniform(0.45, 0.75)))

    @property
    def alive(self):
        return self.age < self.life

    def update(self, dt):
        self.age += dt

    def bounds(self, camera):
        """Рамка пятна на экране (pygame.Rect)."""
        cx, cy = camera.world_to_screen(self.x, self.y)
        r = math.ceil(self.reach * camera.zoom) + 2
        return pygame.Rect(math.floor(cx) - r, math.floor(cy) - r, 2 * r + 1, 2 * r + 1)

    def draw(self, overlay, camera, origin=(0, 0)):
        """origin — экранные координаты левого верхнего угла слоя overlay."""
        z = camera.zoom
        u = self.age / self.life
        cx, cy = camera.world_to_screen(self.x, self.y)
        cx -= origin[0]
        cy -= origin[1]
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

    def update(self, dt):
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