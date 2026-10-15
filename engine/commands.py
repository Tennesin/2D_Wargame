"""engine/commands.py — команда машине и событие выстрела."""
from dataclasses import dataclass
from typing import Optional, Tuple
from .kinds import AmmoKind

# ==========================================
# КОМАНДА МАШИНЕ И СОБЫТИЕ ВЫСТРЕЛА
# ==========================================
@dataclass
class VehicleCommand:
    """Что машине «приказали» в этом кадре. Кто приказал (игрок или бот) — не важно."""
    throttle: float = 0.0                              # -1..1 (назад / вперёд)
    steer: float = 0.0                                 # -1..1 (влево / вправо)
    aim_point: Optional[Tuple[float, float]] = None    # куда целиться (МИРОВЫЕ координаты)
    fire: bool = False                                 # огонь в этом кадре

@dataclass(frozen=True)
class AmmoStats:
    """Готовые числа одного выстрела: орудие (spec) + выбранный тип снаряда.
    Неизменяемый, поэтому один объект можно безопасно раздавать снарядам и интерфейсу."""
    kind: AmmoKind
    damage: float                    # заявленный урон
    penetration: float               # пробитие, мм
    speed_px: float                  # скорость снаряда, px/с
    range_px: float                  # дальность, px (у всех типов одинаковая)
    reload: float                    # перезарядка после выстрела этим снарядом, с
    ricochet: bool = True            # может ли рикошетить (шаг КС)
    aoe_radius_px: float = 0.0       # радиус взрыва по площади, 0 = нет (шаг ФГ)
    min_frac: float = 0.0            # гарантированная доля урона, 0 = нет (шаг ФГ)
    explode_at_range: bool = False   # взрывается на пределе дальности (шаг ФГ)
    module_pen_k: float = 1.0        # множитель пробития после внешнего модуля-гусеницы (1.0 = не влияет)
    screen_pen_k: float = 1.0        # то же для лобового экрана

@dataclass
class Shot:
    """Событие «выстрел»: откуда вылетел снаряд, куда смотрел ствол и чем выстрелили."""
    x: float          # мировые координаты дульного среза
    y: float
    angle: float      # абсолютный угол башни в градусах (0 = вверх, по часовой)
    ammo: Optional[AmmoStats] = None