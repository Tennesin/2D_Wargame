"""game/background/events/broken_track.py — у танка игрока сбивают гусеницу, он останавливается, чинится и едет дальше."""
from ..paths import line
from .registry import event

@event("broken_track", weight=0.7)
def run(stage):
    rng = stage.rng
    y = rng.uniform(0.35, 0.65)
    a, b = (-0.3, 1.3) if rng.random() < 0.5 else (1.3, -0.3)
    mid = rng.uniform(0.4, 0.6)
    me = stage.spawn_player((a, y))
    me.drive(stage.route(line((a, y), (b, y))), speed=0.15)
    yield lambda: abs(stage.frac(me.v.x, me.v.y)[0] - mid) < 0.05      # дошёл до середины экрана
    me.v.tracks.break_track(rng.choice(("left", "right")))
    me.brake()
    yield rng.uniform(1.0, 1.6)
    me.v.start_repair()
    yield lambda: not me.v.tracks.broken                                # ремонт идёт сам (около 5 с)
    fx, fy = stage.frac(me.v.x, me.v.y)
    me.drive(stage.route(line((fx, fy), (b, y))), speed=0.15, face=False)
    yield me.is_done