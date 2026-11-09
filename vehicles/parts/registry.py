"""vehicles/parts/registry.py — реестр типов деталей: ключ, подпись, поверхности, слой, функция рисования, границы размера."""
from dataclasses import dataclass
from typing import Callable, Optional

from .model import CAT_DECOR

@dataclass(frozen=True)
class PartType:
    key: str
    label: str                      # подпись в палитре редактора
    surfaces: tuple                 # на каких поверхностях деталь допустима
    z: int                          # слой по умолчанию
    draw: Callable                  # draw(p: PartPen, part, ctx)
    category: str = CAT_DECOR
    w_range: Optional[tuple] = None # (мин, макс) для w; None: поле не используется
    h_range: Optional[tuple] = None
    step: float = 0.05              # шаг привязки при редактировании

PART_TYPES = {}

def part_type(key, label, *, surfaces, z, category=CAT_DECOR, w=None, h=None, step=0.05):
    """Декоратор: регистрирует функцию рисования как тип детали."""
    def register(fn):
        if key in PART_TYPES:
            raise ValueError(f"тип детали {key!r} уже зарегистрирован")
        PART_TYPES[key] = PartType(key, label, tuple(surfaces), z, fn, category, w, h, step)
        return fn
    return register

def z_of(part):
    """Слой детали: свой или слой её типа (неизвестный тип: -1, рисоваться не будет)."""
    if part.z is not None:
        return part.z
    ptype = PART_TYPES.get(part.kind)
    return ptype.z if ptype is not None else -1