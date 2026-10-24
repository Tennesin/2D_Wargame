"""events — события фона: один файл на событие. Новое событие: создать файл с @event и добавить его в импорт ниже."""
from .registry import EVENTS, Event, event, pick_event
from . import (curvy_player, bot_crossing, assault_pair, barrage, retreat_chase,
               shelled_runner, duel, broken_track, convoy)

__all__ = ["EVENTS", "Event", "event", "pick_event"]