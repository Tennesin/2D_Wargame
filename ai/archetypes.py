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
    weights: dict                     # ключи как в TANK_PARAMS, значения 0..1
    color: tuple                      # цвет башни и маски
    engage_dist_m: float              # желаемая дистанция боя
    flank_bias: float                 # 0..1: охота обходить, если лоб не пробивается
    face_threat: float                # 0..1: держать лоб к врагу (пока не используется)
    strafe: bool = False              # пока не используется
    retreat_hp: float = 0.0           # доля HP, ниже которой бот ищет укрытие (0: никогда)
    jitter: float = 0.06              # разброс весов у каждого экземпляра
    t_anchor: Optional[float] = None  # уровень, на котором архетип равен эталону
    cover_bias: float = 0.0           # склонность прятаться: 0 лезет напролом, 1 осторожный

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

ARCHETYPES = {"universal": UNIVERSAL}     # остальные добавляются сюда по мере готовности