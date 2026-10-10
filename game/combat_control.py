"""game/combat_control.py — эффекты, попадания снарядов, линия прицела, уведомления о боях."""
from combat import EffectsSystem, TargetSet, compute_aim
from .modes import Mode

class CombatController:
    def __init__(self, tank, walls, terrain, modes, fleet, notifier):
        self.tank = tank
        self.walls = walls
        self.modes = modes
        self.fleet = fleet
        self.notifier = notifier
        self.kills = 0
        self.effects = EffectsSystem()
        self.targets = TargetSet(walls, terrain, fleet)

    def update(self, dt):
        hits, ricochets, misses = self.effects.update(dt, self.targets)
        for owner, target in ricochets:
            self.notifier.on_ricochet(owner, target)
        for owner in misses:
            self.notifier.on_miss(owner)
        self._apply_hits(hits)

    def _apply_hits(self, hits):
        """Снаряд попал в цель: урон = заявленный × доля по правилам armor.py (стена и танк одинаково)."""
        if not hits:
            return
        for target, spec, cos_impact, normal, power, owner in hits:
            pen = spec.penetration * power
            res = target.hit_result(pen, cos_impact, normal)          # для сообщения: до изменения hp
            dealt = target.take_hit(pen, spec.damage * power, cos_impact, normal)
            self.notifier.on_hit(owner, target, normal, res, dealt)
        self.walls.remove_dead()
        self.kills += self.fleet.remove_dead()
        if self.modes.mode == Mode.WALL_EDIT and self.walls.selected is None:
            self.modes.set_mode(Mode.DRIVE)

    def aim_info(self):
        """Траектория выстрела. Только в боевом состоянии, не в режиме стройки и пока танк жив."""
        if not self.tank.alive:
            return None
        if not self.modes.combat or self.modes.mode == Mode.BUILD:
            return None
        return compute_aim(self.tank, self.targets)