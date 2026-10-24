"""game/match/context.py — общие объекты игровой партии и единый шаг техники."""
from dataclasses import dataclass

@dataclass
class GameContext:
    camera: object
    terrain: object
    walls: object
    fleet: object
    effects: object
    targets: object
    notifier: object
    settings: object
    match_stats: object

    def obstacles_for(self, vehicle):
        """Прямоугольники стен и чужой техники рядом с vehicle."""
        reach = vehicle.reach_px()
        return (self.walls.obbs_near(vehicle.x, vehicle.y, reach)
                + self.fleet.obbs_near(vehicle, reach))

    def step_vehicle(self, vehicle, command, dt):
        """Обновить технику по команде и, если был выстрел, породить снаряд и эффекты."""
        shot = vehicle.update(command, dt, self.obstacles_for(vehicle), self.terrain)
        if vehicle.repaired_track is not None:
            self.notifier.on_track_repaired(vehicle, vehicle.repaired_track)
        if shot is not None:
            self.effects.spawn_shot(shot, vehicle.spec, vehicle)
        return shot