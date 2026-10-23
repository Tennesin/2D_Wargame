"""combat/effects.py — система снарядов и эффектов: полёт снарядов, попадания, рикошеты, промахи,
создание и отрисовка визуальных частей (см. effect_parts.py)."""
import math
import random
from dataclasses import dataclass
import pygame

from engine import heading_vector, AlphaLayer
from .effect_parts import MuzzleFlash, SmokeStreak, Explosion, Scorch, Spark
from .projectile import Shell

@dataclass
class Impact:
    """Взрыв снаряда. target = None: снаряд взорвался в воздухе (фугас на пределе дальности)."""
    target: object
    stats: object          # AmmoStats выстрела
    cos: float
    normal: object
    power: float           # доля силы (после рикошетов меньше 1)
    owner: object
    x: float               # точка взрыва, мировые px
    y: float

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
        self._alpha = AlphaLayer()
        self._rng = random.Random()

    def spawn_shot(self, shot, spec, tank=None):
        dx, dy = heading_vector(shot.angle)
        origin = (shot.x - dx * spec.MUZZLE_DIST_PX,        # центр танка: оттуда считаем первый отрезок пролёта
                  shot.y - dy * spec.MUZZLE_DIST_PX)
        self.shells.append(Shell(shot.x, shot.y, shot.angle, spec, shot.ammo, origin, owner=tank))
        self.flashes.append(MuzzleFlash(shot.x, shot.y, shot.angle, spec, anchor=tank))
        for _ in range(spec.SMOKE_STREAKS):
            self.smoke.append(SmokeStreak(shot.x, shot.y, shot.angle, spec, self._rng, anchor=tank))

    def _spawn_impact(self, shell):
        stats = shell.stats
        real_blast = shell.hit_target is not None or stats.explode_at_range
        radius = stats.aoe_radius_px if real_blast else 0.0
        self.explosions.append(Explosion(shell.x, shell.y, shell.spec, self._rng, radius))
        self.scorches.append(Scorch(shell.x, shell.y, shell.spec, self._rng, radius))

    def update(self, dt, targets=None):
        """Возвращает три списка:
          попадания: урон применяет Game, а не эффекты;
          рикошеты: снаряд отскочил и летит дальше;
          промахи: снаряд долетел до предела дальности, ничего не задев."""
        for shell in self.shells:
            shell.update(dt, targets)
        for group in (self.flashes, self.smoke, self.explosions, self.scorches, self.sparks):
            for obj in group:
                obj.update(dt)

        hits, ricochets, misses = [], [], []
        for shell in self.shells:
            if shell.ricochet_at is not None:             # отскок: только искры, без взрыва
                self.sparks.append(Spark(*shell.ricochet_at, shell.dx, shell.dy, self._rng))
                ricochets.append((shell.owner, shell.ricochet_target))
                shell.ricochet_at = None
                shell.ricochet_target = None
            if shell.exploded:
                self._spawn_impact(shell)
                if shell.hit_target is not None or shell.stats.explode_at_range:
                    hits.append(Impact(shell.hit_target, shell.stats, shell.hit_cos,
                                       shell.hit_normal, shell.power, shell.owner,
                                       shell.x, shell.y))
                elif shell.bounces == 0:
                    misses.append(shell.owner)

        self.shells = [o for o in self.shells if o.alive]
        self.flashes = [o for o in self.flashes if o.alive]
        self.smoke = [o for o in self.smoke if o.alive]
        self.explosions = [o for o in self.explosions if o.alive]
        self.scorches = [o for o in self.scorches if o.alive]
        self.sparks = [o for o in self.sparks if o.alive]
        return hits, ricochets, misses

    def draw_ground(self, screen, camera):
        """Всё, что лежит на земле (рисуется ДО танка, чтобы пятна были под ним)."""
        if not self.scorches:
            return
        view = screen.get_rect()
        items = [(s, s.bounds(camera)) for s in self.scorches]
        items = [(s, r) for s, r in items if r.colliderect(view)]
        if not items:
            return
        area = items[0][1].unionall([r for _, r in items[1:]]).clip(view)
        if area.w <= 0 or area.h <= 0:
            return
        layer = self._alpha.begin(area.size)
        for s, _ in items:
            s.draw(layer, camera, area.topleft)
        screen.blit(layer, area.topleft)

    def _draw_smoke(self, screen, camera):
        lines = [p for p in (s.prepare(camera) for s in self.smoke) if p is not None]
        if not lines:
            return
        xs = [x for pts, _, _ in lines for x, _ in pts]
        ys = [y for pts, _, _ in lines for _, y in pts]
        pad = max(w for _, _, w in lines) + 2
        x0, y0 = math.floor(min(xs)) - pad, math.floor(min(ys)) - pad
        w, h = math.ceil(max(xs)) - x0 + pad + 1, math.ceil(max(ys)) - y0 + pad + 1
        area = pygame.Rect(x0, y0, w, h).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        layer = self._alpha.begin(area.size)
        for pts, color, width in lines:
            shifted = [(x - area.x, y - area.y) for x, y in pts]
            pygame.draw.lines(layer, color, False, shifted, width)
        screen.blit(layer, area.topleft)

    def draw(self, screen, camera):
        """Всё, что летит и горит (рисуется ПОСЛЕ танка)."""
        self._draw_smoke(screen, camera)
        for shell in self.shells:
            shell.draw(screen, camera)
        for boom in self.explosions:
            boom.draw(screen, camera)
        for flash in self.flashes:
            flash.draw(screen, camera)
        for spark in self.sparks:
            spark.draw(screen, camera)