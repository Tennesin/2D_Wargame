"""vehicles/look.py — «уровни оформления» танка: что дорисовывать поверх базового спрайта."""
from typing import NamedTuple

def level(value, thresholds):
    """Сколько порогов превышено: 0, 1, 2…"""
    return sum(value > t for t in thresholds)

class Look(NamedTuple):
    front: int = 0
    side: int = 0
    gun: int = 0
    speed: int = 0
    screen: int = 0    # лобовые экраны: 0 нет, 1..3 по толщине

    @property
    def hull_key(self): return (self.front, self.side, self.speed, self.screen)
    @property
    def turret_key(self): return (self.front, self.speed)
    @property
    def barrel_key(self): return self.gun