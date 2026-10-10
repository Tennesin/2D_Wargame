"""ai/counter.py — «умный» спавн: профиль игрока -> множители шансов архетипов."""
from engine import clamp
from vehicles import TANK_PARAMS

# При каком отношении к эталону уровень «угрозы» становится максимальным (1.0).
# Значения совпадают с верхними порогами LOOK_*_RATIO в vehicles/tank/params.py.
FULL_ARMOR_RATIO = 1.40     # лоб относительно эталона
FULL_GUN_RATIO = 1.35       # калибр относительно эталона
FULL_SPEED_RATIO = 2.2      # удельная мощность относительно эталона

_REF_FRONT = TANK_PARAMS["front_armor_mm"].default
_REF_CAL = TANK_PARAMS["gun_caliber_mm"].default

# Что спавнить против каждой «выкрученной» характеристики игрока.
# Число: насколько растёт множитель шанса при максимальном уровне (отрицательное: шанс падает).
COUNTERS = {
    "armor": {"destroyer": 2.0, "bunker": 1.5, "scout": -0.5},
    "gun":   {"bunker": 1.5, "universal": 0.5},
    "speed": {"scout": 2.0, "universal": 1.0, "bunker": -0.3},
}

MIN_MULT = 0.15     # шанс архетипа не падает ниже 15% от обычного
MAX_MULT = 4.0      # и не растёт больше чем в 4 раза


def _level(ratio, full):
    """0 на эталоне и ниже, 1 при ratio >= full, между ними линейно."""
    return clamp((ratio - 1.0) / (full - 1.0), 0.0, 1.0)


def threat_profile(spec):
    """Насколько игрок «выкручен» по каждой оси: {"armor": 0..1, "gun": 0..1, "speed": 0..1}."""
    return {
        "armor": _level(spec.front / _REF_FRONT, FULL_ARMOR_RATIO),
        "gun": _level(spec.cal / _REF_CAL, FULL_GUN_RATIO),
        "speed": _level(spec.q_pw, FULL_SPEED_RATIO),
    }


def counter_multipliers(profile, archetypes):
    """Множитель шанса для каждого ключа архетипа. У игрока на эталоне все множители равны 1.0."""
    mult = {key: 1.0 for key in archetypes}
    for trait, level in profile.items():
        for key, bonus in COUNTERS[trait].items():
            if key in mult:
                mult[key] += bonus * level
    return {key: clamp(v, MIN_MULT, MAX_MULT) for key, v in mult.items()}