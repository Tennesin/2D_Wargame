"""game/background/events/assault_pair.py — два штурмовых ПТ-САУ спускаются сверху вниз и расходятся по бокам."""
from ..paths import bezier
from .registry import event

@event("assault_pair", weight=1.0)
def run(stage):
    rng = stage.rng
    cx = rng.uniform(0.4, 0.6)
    turn_y = rng.uniform(0.3, 0.5)
    pair = []
    for side in (-1, 1):
        x = cx + side * 0.04
        route = bezier((x, -0.3), (x, turn_y + 0.2), (x + side * 0.12, turn_y + 0.15), (x + side * 0.45, 1.3))
        tank = stage.spawn_bot("assault", route[0])
        tank.drive(stage.route(route), speed=0.12)
        pair.append(tank)
        yield 0.35
    yield 1.2
    for tank in pair:
        tank.fire()
    yield stage.all_done(*pair)