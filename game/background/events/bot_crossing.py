"""game/background/events/bot_crossing.py — танк бота проезжает слева направо."""
from ..paths import wave
from .registry import event

@event("bot_crossing", weight=1.5)
def run(stage):
    rng = stage.rng
    key = rng.choice(("universal", "scout", "destroyer", "bunker", "sniper"))
    y = rng.uniform(0.2, 0.8)
    route = wave((-0.3, y), (1.3, y + rng.uniform(-0.1, 0.1)), amp=0.03, waves=1.0)
    bot = stage.spawn_bot(key, route[0])
    bot.drive(stage.route(route), speed=0.14)
    if rng.random() < 0.5:
        yield rng.uniform(1.0, 2.5)
        bot.fire()
    yield bot.is_done