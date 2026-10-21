"""game/combat_control.py — попадания снарядов, линия прицела, уведомления о боях."""

from engine import TargetType
from combat import compute_aim, splash_damage, pen_after_modules
from .modes import Mode

class CombatController:
    def __init__(self, ctx, modes):
        self.tank = ctx.fleet.player
        self.walls = ctx.walls
        self.modes = modes
        self.fleet = ctx.fleet
        self.notifier = ctx.notifier
        self.effects = ctx.effects
        self.targets = ctx.targets

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
        pen = pen_after_modules(target, full_pen, stats, im.x, im.y)   # КС на гусенице: пробитие ×0.5
        res = target.hit_result(pen, im.cos, im.normal)
        dealt = target.take_hit(pen, stats.damage * im.power, im.cos, im.normal, stats.min_frac)
        if pen < full_pen:
            self.notifier.on_module_absorb(im.owner, target, target.module_at(im.x, im.y))
        self.notifier.on_hit(im.owner, target, im.normal, res, dealt, stats.min_frac)
        if target.target_type is TargetType.VEHICLE and target.alive:
            side = target.knock_track(im.x, im.y)
            if side is not None:
                self.notifier.on_track_broken(im.owner, target, side)
            if stats.stun_s > 0.0:
                target.apply_stun(stats.stun_s)
                self.notifier.on_stun(im.owner, target)

    def _splash(self, im):
        """Осколки по всем целям в радиусе. Прямая цель пропускается: она уже получила
        max(доля по броне, минимум), поэтому двойного урона нет."""
        stats = im.stats
        base = stats.damage * im.power
        for target, dist in self.targets.in_circle(im.x, im.y, stats.aoe_radius_px, ignore=im.owner):
            if target is im.target:
                continue
            dealt = splash_damage(base, stats.min_frac, dist, stats.aoe_radius_px)
            if dealt <= 0.0:
                continue
            target.take_damage(dealt)
            self.notifier.on_splash(im.owner, target, dealt)

    def aim_info(self):
        """Траектория выстрела. Только в боевом состоянии, не в режиме стройки и пока танк жив."""
        if not self.tank.alive:
            return None
        if not self.modes.combat or self.modes.mode == Mode.BUILD:
            return None
        return compute_aim(self.tank, self.targets)