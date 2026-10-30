"""engine/commands.py — команда машине и событие выстрела."""
from dataclasses import dataclass
from typing import Optional, Tuple, Union
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
    range_px: float                  # дальность, px
    reload: float                    # перезарядка после выстрела этим снарядом, с
    ricochet: bool = True            # может ли рикошетить (у КС, HESH и ФГ нет)
    aoe_radius_px: float = 0.0       # радиус взрыва по площади, 0 = нет (ФГ и HESH)
    min_frac: float = 0.0            # гарантированная доля урона, 0 = нет (ФГ и HESH)
    explode_at_range: bool = False   # взрывается на пределе дальности (ФГ)
    module_pen_k: float = 1.0        # множитель пробития после внешнего модуля-гусеницы (1.0 = не влияет)
    screen_pen_k: float = 1.0        # то же для лобового экрана
    stun_s: float = 0.0             # длительность оглушения цели при прямом попадании, с
    caliber_mm: float = 0.0          # калибр орудия (для урона осколков фугасов)
    normalization_deg: float = 0.0   # доворот к нормали при попадании, градусы
    splash_frac: float = 0.0         # доля урона осколков в центре (ФГ и HESH)
    splash_armor_ref_mm: float = 0.0 # >0: осколки ослабляются бронёй (ФГ); 0: броня не учитывается (HESH)

@dataclass(frozen=True)
class ArtilleryStats:
    """Готовые числа выстрела САУ (неизменяемые, как AmmoStats). Размеры и скорость в мировых px."""
    damage: float              # урон в зоне максимальной эффективности
    inner_radius_px: float     # радиус зоны максимума (полный урон и оглушение)
    outer_radius_px: float     # внешний радиус взрыва
    speed_px: float            # скорость полёта по земле, px/с
    reload: float              # перезарядка, с
    stun_s: float              # оглушение в зоне максимума, с
    range_min_px: float        # мёртвая зона вокруг САУ
    range_max_px: float        # максимальная дальность
    caliber_mm: float
    edge_k: float = 0.25       # доля урона на границе внешнего радиуса (combat/artillery.py)
    wall_k: float = 1.5        # множитель урона по стенам
    armor_ref_mm: float = 50.0 # опорная броня для ослабления урона в кольце

@dataclass
class Shot:
    """Событие «выстрел»: откуда вылетел снаряд, куда смотрел ствол и чем выстрелили.
    target задан только у САУ: точка на земле (мировые px), куда упадёт снаряд."""
    x: float          # мировые координаты дульного среза
    y: float
    angle: float      # абсолютный угол орудия в градусах (0 = вверх, по часовой)
    ammo: Optional[Union[AmmoStats, ArtilleryStats]] = None
    target: Optional[Tuple[float, float]] = None