"""engine/param.py — описание параметра-ползунка."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Param:
    label: str       # подпись на панели
    unit: str        # единица измерения
    min: float
    max: float
    default: float   # стартовое значение
    step: float      # шаг ползунка
    decimals: int = 0   # знаков после запятой на панели
