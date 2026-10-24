"""game/background/events/curvy_player.py — танк игрока проезжает по кривой линии через весь экран."""
import math

from ..paths import wave
from .registry import event

@event("curvy_player", weight=1.2)
def run(stage):
    rng = stage.rng
    x0, x1 = (-0.3, 1.3) if rng.random() < 0.5 else (1.3, -0.3)
    route = wave((x0, rng.uniform(0.25, 0.75)), (x1, rng.uniform(0.25, 0.75)),
                 amp=rng.uniform(0.10, 0.20), waves=rng.uniform(1.0, 2.0),
                 phase=rng.uniform(0.0, math.tau))
    me = stage.spawn_player(route[0])
    me.drive(stage.route(route), speed=0.15)
    if rng.random() < 0.6:                                   # иногда по пути стреляет в случайную точку
        yield rng.uniform(1.0, 3.0)
        me.aim_at(stage.pt(rng.uniform(0.2, 0.8), rng.uniform(0.1, 0.9)))
        me.fire()
    yield me.is_done