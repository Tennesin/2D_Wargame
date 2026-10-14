"""tank/look.py — «уровни оформления» танка: что дорисовывать поверх базового спрайта."""
from typing import NamedTuple

def level(value, thresholds):
    """Сколько порогов превышено: 0, 1, 2…"""
    return sum(value > t for t in thresholds)

class Look(NamedTuple):
    front: int = 0     # накладная броня лба и утолщённая башня
    side: int = 0      # бортовые экраны
    gun: int = 0       # дульный тормоз
    speed: int = 0     # выхлоп и антенна

    # ключи кэшей: в них входят только те уровни, которые меняют конкретный спрайт
    @property
    def hull_key(self): return (self.front, self.side, self.speed)
    @property
    def turret_key(self): return (self.front, self.speed)
    @property
    def barrel_key(self): return self.gun