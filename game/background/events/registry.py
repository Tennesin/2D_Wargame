"""game/background/events/registry.py — реестр событий фона: декоратор @event и взвешенный выбор без повторов.
Событие: функция run(stage), генератор. yield число = пауза в секундах; yield функция = ждать, пока вернёт True."""
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class Event:
    key: str
    weight: float
    run: Callable

EVENTS = {}

def event(key, weight=1.0):
    """Регистрирует событие. weight: относительная частота (залп САУ реже, проезд бота чаще)."""
    def register(fn):
        EVENTS[key] = Event(key, weight, fn)
        return fn
    return register

def pick_event(history, rng):
    """Случайное событие, которого нет среди недавних (history). Если выбирать не из чего, берём любое."""
    pool = [e for e in EVENTS.values() if e.key not in history]
    if not pool:
        pool = list(EVENTS.values())
    return rng.choices(pool, weights=[e.weight for e in pool])[0]