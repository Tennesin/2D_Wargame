"""game/background/events/shelled_runner.py — танк игрока едет, а вокруг него ложатся снаряды САУ (близкие промахи)."""
import math

from ..paths import wave
from .registry import event

@event("shelled_runner", weight=0.6)
def run(stage):
    rng = stage.rng
    x0, x1 = (-0.3, 1.3) if rng.random() < 0.5 else (1.3, -0.3)
    route = wave((x0, rng.uniform(0.3, 0.7)), (x1, rng.uniform(0.3, 0.7)),
                 amp=rng.uniform(0.08, 0.15), waves=1.5, phase=rng.uniform(0.0, math.tau))
    me = stage.spawn_player(route[0])
    me.drive(stage.route(route), speed=0.16)
    yield 1.0
    for _ in range(rng.randint(4, 6)):
        if me.removed:
            break
        stage.shell_at(me, scatter_m=rng.uniform(5.0, 10.0), cal=170)
        yield rng.uniform(0.5, 0.9)
    yield me.is_done