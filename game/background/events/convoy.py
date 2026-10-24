"""game/background/events/convoy.py — колонна: ведущий бот и два ведомых, идущих уступом."""
from ..paths import wave
from .registry import event

@event("convoy", weight=1.0)
def run(stage):
    rng = stage.rng
    key = rng.choice(("universal", "scout", "destroyer", "bunker"))
    y = rng.uniform(0.3, 0.7)
    a, b = (-0.3, 1.3) if rng.random() < 0.5 else (1.3, -0.3)
    heading = 90 if b > a else 270
    route = wave((a, y), (b, y + rng.uniform(-0.1, 0.1)), amp=0.05, waves=1.0)

    leader = stage.spawn_bot(key, route[0], heading=heading)
    leader.drive(stage.route(route), speed=0.11)
    crew = [leader]
    for lateral in (-5.0, 5.0):
        yield 1.4
        follower = stage.spawn_bot(key, route[0], heading=heading)
        follower.chase(leader, gap_m=16.0, lateral_m=lateral)
        crew.append(follower)
    yield stage.all_done(*crew)