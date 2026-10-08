"""engine/commands.py — команда машине и событие выстрела."""
from dataclasses import dataclass
from typing import Optional, Tuple

# ==========================================
# КОМАНДА МАШИНЕ И СОБЫТИЕ ВЫСТРЕЛА
# ==========================================
@dataclass
class VehicleCommand:
    """Что машине «приказали» в этом кадре. Кто приказал (игрок или бот) — не важно."""
    throttle: float = 0.0                              # -1..1 (назад / вперёд)
    steer: float = 0.0                                 # -1..1 (влево / вправо)
    aim_point: Optional[Tuple[float, float]] = None    # куда целиться (МИРОВЫЕ координаты)
    fire: bool = False                                 # задел под стрельбу

@dataclass
class Shot:
    """Событие «выстрел»: откуда вылетел снаряд и куда смотрел ствол."""
    x: float          # мировые координаты дульного среза
    y: float
    angle: float      # абсолютный угол башни в градусах (0 = вверх, по часовой)