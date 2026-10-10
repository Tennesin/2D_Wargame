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
    face_threat: float                  # 0..1: держать лоб к врагу (пока не используется)
    strafe: bool = False                # пока не используется
    retreat_hp: float = 0.0             # доля HP, ниже которой бот ищет укрытие (0: никогда)
    jitter: float = 0.06                # разброс весов у каждого экземпляра
    t_anchor: Optional[float] = None    # уровень, на котором архетип равен эталону
    cover_bias: float = 0.0             # склонность прятаться: 0 лезет напролом, 1 осторожный
    budget_k: float = 1.0               # множитель бюджета (Бункер дороже, Разведчик дешевле)
    spawn_weight: float = 1.0           # относительная частота появления
    edge_k: float = 1.0                 # насколько характеристики сдвигают дистанцию боя (0: ровно engage_dist_m)

@dataclass(frozen=True)
class Skill:
    reaction: tuple = (0.4, 0.9)      # задержка перед первым выстрелом по новой линии огня, с
    lead_k: float = 0.8               # качество упреждения: 1.0 идеально
    think_hz: float = 8.0             # как часто бот «думает»

DEFAULT_SKILL = Skill()

_w, _t = _reference_weights()
UNIVERSAL = Archetype("Универсал", _w, (70, 120, 210),
                      engage_dist_m=22.0, flank_bias=0.3, face_threat=0.6,
                      jitter=0.0, t_anchor=_t, retreat_hp=0.35, cover_bias=0.3)

BUNKER = Archetype(
    "Бункер",
    {"gun_caliber_mm": 0.45, "front_armor_mm": 1.0, "side_armor_mm": 0.9,
     "rear_armor_mm": 0.7, "engine_power_hp": 0.8},
    (36, 66, 150),
    engage_dist_m=16.0, flank_bias=0.0, face_threat=1.0,
    retreat_hp=0.0, cover_bias=0.0,
    budget_k=1.4, spawn_weight=0.5, edge_k=0.3)

DESTROYER = Archetype(
    "Уничтожитель",
    {"gun_caliber_mm": 1.0, "front_armor_mm": 0.30, "side_armor_mm": 0.10,
     "rear_armor_mm": 0.08, "engine_power_hp": 0.7},
    (60, 90, 225),
    engage_dist_m=28.0, flank_bias=0.2, face_threat=0.3,
    retreat_hp=0.5, cover_bias=0.8,
    budget_k=1.0, spawn_weight=0.8, edge_k=0.3)

SCOUT = Archetype(
    "Разведчик",
    {"gun_caliber_mm": 0.35, "front_armor_mm": 0.15, "side_armor_mm": 0.10,
     "rear_armor_mm": 0.08, "engine_power_hp": 1.0},
    (110, 175, 235),
    engage_dist_m=26.0, flank_bias=0.8, face_threat=0.2,
    retreat_hp=0.3, cover_bias=0.2,
    budget_k=0.6, spawn_weight=1.2, edge_k=1.0)

ARCHETYPES = {"universal": UNIVERSAL, "bunker": BUNKER,
              "destroyer": DESTROYER, "scout": SCOUT}