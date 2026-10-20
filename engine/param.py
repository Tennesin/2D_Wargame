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

    def fit(self, value, unbounded=False):
        """Привести значение к границам ползунка. unbounded=True: верхней границы нет (для ботов)."""
        value = float(value)
        if unbounded:
            return max(value, self.min)
        return min(self.max, max(self.min, value))
