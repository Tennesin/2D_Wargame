"""game/background/events/retreat_chase.py — танк игрока уходит справа налево и стреляет назад,
а следом его догоняют Универсал и Разведчик."""
from ..paths import wave
from .registry import event

@event("retreat_chase", weight=0.9)
def run(stage):
    rng = stage.rng
    y = rng.uniform(0.35, 0.65)
    route = wave((1.3, y), (-0.3, y + rng.uniform(-0.08, 0.08)), amp=0.04, waves=1.0)
    me = stage.spawn_player(route[0])
    me.drive(stage.route(route), speed=0.15)
    me.aim_dir(90)                                           # башня смотрит назад (вправо)
    me.snap_turret(90)                                       # сразу, без долгого разворота
    yield 0.9
    chasers = []
    for key, gap, lateral in (("universal", 22.0, -4.0), ("scout", 36.0, 5.0)):
        c = stage.spawn_bot(key, (1.35, y + rng.uniform(-0.04, 0.04)), heading=270)
        c.chase(me, gap_m=gap, lateral_m=lateral)
        c.aim_actor(me)
        chasers.append(c)
        yield 0.6
    yield 1.0
    me.fire(2)
    yield 1.5
    for c in chasers:
        c.fire()
    yield me.is_done