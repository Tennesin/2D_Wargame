"""game/background/events/barrage.py — залп: 10 САУ по очереди (пауза 0.15 с) накрывают большую часть поля."""
from .registry import event

@event("barrage", weight=0.6)
def run(stage):
    cal = stage.rng.choice((170, 200, 230))
    for target in stage.jittered_grid(cols=5, rows=2, cover=0.9):
        stage.fire_artillery(target, cal=cal)
        yield 0.15