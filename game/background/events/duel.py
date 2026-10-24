"""game/background/events/duel.py — игрок и бот разъезжаются по соседним полосам, сближаются и стреляют на ходу."""
from ..paths import wave
from .registry import event

@event("duel", weight=0.8)
def run(stage):
    rng = stage.rng
    top = rng.uniform(0.20, 0.30)                 # верхняя полоса (доли высоты экрана)
    bottom = top + rng.uniform(0.30, 0.38)        # нижняя: расстояние между полосами больше двух габаритов танка
    drift = rng.uniform(-0.04, 0.04)              # одинаковый наклон: полосы остаются параллельными
    ya, yb = (top, bottom) if rng.random() < 0.5 else (bottom, top)

    me = stage.spawn_player((-0.3, ya))
    foe = stage.spawn_bot(rng.choice(("universal", "destroyer", "bunker", "scout")), (1.3, yb))
    me.drive(stage.route(wave((-0.3, ya), (1.3, ya + drift), amp=0.02, waves=1.0)), speed=0.10)
    foe.drive(stage.route(wave((1.3, yb), (-0.3, yb + drift), amp=0.02, waves=1.0)), speed=0.10)
    me.aim_actor(foe)
    foe.aim_actor(me)

    # стреляют, только когда оба на экране и снаряды долетают
    yield lambda: (me.visible() and foe.visible()
                   and me.in_range(foe) and foe.in_range(me))
    me.fire(2, timeout=12.0)
    foe.fire(2, timeout=12.0)
    yield stage.all_done(me, foe)