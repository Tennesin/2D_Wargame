"""game/background/events/duel.py — игрок и бот разъезжаются во встречных направлениях и стреляют друг в друга."""
from ..paths import wave
from .registry import event

@event("duel", weight=0.8)
def run(stage):
    rng = stage.rng
    ya, yb = rng.uniform(0.3, 0.45), rng.uniform(0.55, 0.7)
    if rng.random() < 0.5:
        ya, yb = yb, ya
    me = stage.spawn_player((-0.3, ya))
    foe = stage.spawn_bot(rng.choice(("universal", "destroyer", "bunker", "scout")), (1.3, yb))
    me.drive(stage.route(wave((-0.3, ya), (1.3, yb), amp=0.03, waves=1.0)), speed=0.10)
    foe.drive(stage.route(wave((1.3, yb), (-0.3, ya), amp=0.03, waves=1.0)), speed=0.10)
    me.aim_actor(foe)
    foe.aim_actor(me)
    yield 1.2
    me.fire(2)
    foe.fire(2)
    yield stage.all_done(me, foe)