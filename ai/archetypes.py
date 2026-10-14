"""ai/archetypes.py — архетипы: профиль сборки + доктрина поведения."""
from dataclasses import dataclass
from typing import Optional

from vehicles import TANK_PARAMS

def _reference_weights():
    """Доли ползунков эталона, поделённые на максимальную: w * t_anchor = доля эталона."""
    frac = {k: (p.default - p.min) / (p.max - p.min) for k, p in TANK_PARAMS.items()}
    top = max(frac.values())
    return {k: v / top for k, v in frac.items()}, top

@dataclass(frozen=True)
class Archetype:
    name: str
    weights: dict                       # ключи как в TANK_PARAMS, значения 0..1
    color: tuple                        # цвет башни и маски
    engage_dist_m: float                # желаемая дистанция боя
    flank_bias: float                   # 0..1: охота обходить, если лоб не пробивается
    retreat_hp: float = 0.0             # доля HP, ниже которой бот ищет укрытие (0: никогда)
    jitter: float = 0.06                # разброс весов у каждого экземпляра
    t_anchor: Optional[float] = None    # уровень, на котором архетип равен эталону
    cover_bias: float = 0.0             # склонность прятаться: 0 лезет напролом, 1 осторожный
    budget_k: float = 1.0               # множитель бюджета (Бункер дороже, Разведчик дешевле)
    spawn_weight: float = 1.0           # относительная частота появления
    edge_k: float = 1.0                 # насколько характеристики сдвигают дистанцию боя (0: ровно engage_dist_m)
    aspect_deg: float = 90.0            # куда стремится: 0 лоб, 90 борт, 180 корма
    aspect_tol_deg: float = 30.0        # допуск: в этих пределах бот считается «на позиции»
    aspect_drive: float = 0.0           # постоянная тяга к позиции (балл намерения FLANK)
    damage_band: tuple = (0.5, 0.5)     # где на ползунке урона (0..1 внутри коридора калибра) выбирается значение
    pen_band: tuple = (0.5, 0.5)        # то же для пробития
    emblem: str = ""                    # деталь на башне для узнавания: "" нет, "chevron" и т.д.

@dataclass(frozen=True)
class Skill:
    reaction: tuple = (0.4, 0.9)      # задержка перед первым выстрелом по новой линии огня, с
    lead_k: float = 0.8               # качество упреждения: 1.0 идеально
    think_hz: float = 8.0             # как часто бот «думает»

DEFAULT_SKILL = Skill()

_w, _t = _reference_weights()

UNIVERSAL = Archetype(
    "Универсал", _w, (64, 140, 200),
    engage_dist_m=22.0, flank_bias=0.3,
    jitter=0.0, t_anchor=_t, retreat_hp=0.35, cover_bias=0.3,
    aspect_deg=150.0, aspect_tol_deg=30.0, aspect_drive=1.6,
    damage_band=(0.40, 0.60), pen_band=(0.40, 0.60))

BUNKER = Archetype(
    "Бункер",
    {"gun_caliber_mm": 0.45, "front_armor_mm": 1.0, "side_armor_mm": 0.9,
     "rear_armor_mm": 0.7, "engine_power_hp": 0.8},
    (36, 66, 150),
    engage_dist_m=16.0, flank_bias=0.0,
    retreat_hp=0.0, cover_bias=0.0,
    budget_k=1.4, spawn_weight=0.5, edge_k=0.3,
    aspect_deg=0.0, aspect_tol_deg=35.0, aspect_drive=3.0,
    damage_band=(0.40, 0.60), pen_band=(0.40, 0.60))

DESTROYER = Archetype(
    "Уничтожитель",
    {"gun_caliber_mm": 1.0, "front_armor_mm": 0.30, "side_armor_mm": 0.10,
     "rear_armor_mm": 0.08, "engine_power_hp": 0.7},
    (96, 72, 214),
    engage_dist_m=28.0, flank_bias=0.2,
    retreat_hp=0.5, cover_bias=0.8,
    budget_k=1.0, spawn_weight=0.8, edge_k=0.3,
    aspect_deg=120.0, aspect_tol_deg=60.0, aspect_drive=0.8,
    damage_band=(0.80, 1.00), pen_band=(0.80, 1.00), emblem="chevron")

SCOUT = Archetype(
    "Разведчик",
    {"gun_caliber_mm": 0.35, "front_armor_mm": 0.15, "side_armor_mm": 0.10,
     "rear_armor_mm": 0.08, "engine_power_hp": 1.0},
    (110, 175, 235),
    engage_dist_m=26.0, flank_bias=0.8,
    retreat_hp=0.3, cover_bias=0.2,
    budget_k=0.6, spawn_weight=1.2, edge_k=1.0,
    aspect_deg=165.0, aspect_tol_deg=25.0, aspect_drive=2.5,
    damage_band=(0.00, 0.25), pen_band=(0.40, 0.60))

ARCHETYPES = {"universal": UNIVERSAL, "bunker": BUNKER,
              "destroyer": DESTROYER, "scout": SCOUT}