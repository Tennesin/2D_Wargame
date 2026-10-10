"""game/combat_control.py — эффекты, попадания снарядов, линия прицела."""
from combat import EffectsSystem, TargetSet, compute_aim
from .modes import Mode

class CombatController:
    def __init__(self, tank, walls, terrain, modes, fleet):
        self.tank = tank
        self.walls = walls
        self.modes = modes
        self.fleet = fleet
        self.kills = 0
        self.effects = EffectsSystem()
        self.targets = TargetSet(walls, terrain, fleet)

    def update(self, dt):
        hits = self.effects.update(dt, self.targets)
        self._apply_hits(hits)

    def _apply_hits(self, hits):
        """Снаряд попал в цель: урон = заявленный × доля по правилам armor.py (стена и танк одинаково)."""
        if not hits:
            return
        for target, spec, cos_impact, normal, power in hits:
            target.take_hit(spec.penetration * power, spec.damage * power, cos_impact, normal)
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