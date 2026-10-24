"""game/match/control/hits.py — попадания снарядов, линия прицела, уведомления о боях."""
import math

from engine import TargetType
from combat import compute_aim, splash_damage, pen_after_modules
from ..modes import Mode

SPLASH_ORIGIN_PUSH_PX = 3.0      # на сколько px точка взрыва отодвигается от грани, в которую попал снаряд

class CombatController:
    def __init__(self, ctx, modes):
        self.tank = ctx.fleet.player
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.modes = modes
        self.fleet = ctx.fleet
        self.notifier = ctx.notifier
        self.effects = ctx.effects
        self.targets = ctx.targets
        self.settings = ctx.settings

    def update(self, dt):
        hits, ricochets, misses = self.effects.update(dt, self.targets)
        for owner, target in ricochets:
            self.notifier.on_ricochet(owner, target)
        for owner in misses:
            self.notifier.on_miss(owner)
        self._apply_hits(hits)

    def _apply_hits(self, impacts):
        """Попадание: прямой урон по правилам armor.py (стена и танк одинаково), затем взрыв, если он есть."""
        if not impacts:
            return
        for im in impacts:
            if im.target is not None:
                self._direct_hit(im)
            if im.stats.aoe_radius_px > 0.0:
                self._splash(im)
        self.walls.remove_dead()
        self.fleet.remove_dead()

    def _direct_hit(self, im):
        stats, target = im.stats, im.target
        full_pen = stats.penetration * im.power
        pen = pen_after_modules(target, full_pen, stats, im.x, im.y)
        res = target.hit_result(pen, im.cos, im.normal)
        dealt = target.take_hit(pen, stats.damage * im.power, im.cos, im.normal,
                                stats.min_frac, stats.caliber_mm)
        if pen < full_pen:
            self.notifier.on_module_absorb(im.owner, target, target.module_at(im.x, im.y))
        self.notifier.on_hit(im.owner, target, im.normal, res, dealt, stats.min_frac)
        if target.target_type is TargetType.VEHICLE and target.alive:
            side = target.knock_track(im.x, im.y)
            if side is not None:
                self.notifier.on_track_broken(im.owner, target, side)
            if stats.stun_s > 0.0:                       # оглушает только прямое попадание, осколки нет
                target.apply_stun(stats.stun_s)
                self.notifier.on_stun(im.owner, target)

    # ---------- осколки ----------
    def _splash(self, im):
        """Осколки по всем целям в радиусе. Прямая цель пропускается: она уже получила
        max(доля по броне, минимум), поэтому двойного урона нет. Цель, закрытая от взрыва
        стеной или камнем, осколков не получает (танки преградой не считаются)."""
        stats = im.stats
        base = stats.damage * im.power
        ox, oy = self._splash_origin(im)
        shooter = None if self.settings.friendly_fire else im.owner
        for target, dist in self.targets.in_circle(im.x, im.y, stats.aoe_radius_px, ignore=shooter):
            if target is im.target:
                continue
            if not self._splash_reaches(ox, oy, target):
                continue
            dealt = splash_damage(base, stats.min_frac, dist, stats.aoe_radius_px)
            if dealt <= 0.0:
                continue
            target.take_damage(dealt)
            self.notifier.on_splash(im.owner, target, dealt)

    @staticmethod
    def _splash_origin(im):
        """Точка, из которой идут лучи осколков: взрыв, чуть отодвинутый от грани, в которую попали.
        Иначе взрыв на самой поверхности стены считал бы начало луча «внутри» неё."""
        if im.normal is None:
            return im.x, im.y
        return (im.x + im.normal[0] * SPLASH_ORIGIN_PUSH_PX,
                im.y + im.normal[1] * SPLASH_ORIGIN_PUSH_PX)

    @staticmethod
    def _probe_points(target):
        """Пробные точки цели: центр и четыре угла её прямоугольника (у танка корпус, у стены сама стена)."""
        get_obb = getattr(target, "hull_obb", None) or target.obb
        cx, cy, hw, hl, ang = get_obb()
        rad = math.radians(ang)
        c, s = math.cos(rad), math.sin(rad)
        points = [(cx, cy)]
        for su in (-1.0, 1.0):
            for sv in (-1.0, 1.0):
                u, v = su * hw, sv * hl
                points.append((cx + u * c - v * s, cy + u * s + v * c))
        return points

    def _splash_reaches(self, ox, oy, target):
        """Дошли ли осколки до цели: хотя бы одна пробная точка видна из точки взрыва."""
        for px, py in self._probe_points(target):
            if not self._solid_between(ox, oy, px, py, target):
                return True
        return False

    def _solid_between(self, ox, oy, px, py, target):
        """Есть ли на пути от (ox, oy) до (px, py) стена или камень (кроме самой цели).
        Берётся ближайшая преграда: если первой на пути стоит сама цель, путь свободен."""
        best_obj, best_t = None, None
        hit = self.walls.raycast(ox, oy, px, py)
        if hit is not None:
            best_obj, best_t = hit[0], hit[1]
        hit = self.terrain.raycast(ox, oy, px, py)
        if hit is not None and (best_t is None or hit[1] < best_t):
            best_obj = hit[0]
        return best_obj is not None and best_obj is not target

    def aim_info(self):
        """Траектория выстрела. Только в боевом состоянии, не в режиме стройки и пока танк жив."""
        if not self.tank.alive:
            return None
        if not self.modes.combat or self.modes.mode == Mode.BUILD:
            return None
        return compute_aim(self.tank, self.targets)