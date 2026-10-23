"""ai/counter.py — «умный» спавн: профиль игрока -> множители шансов архетипов."""
from engine import clamp
from vehicles import VEHICLE_TYPES, LOOK_FRONT_RATIO, LOOK_GUN_RATIO, LOOK_SPEED_RATIO

# Уровень «угрозы» максимален на верхних порогах оформления танка (vehicles/tank/params.py).
# У ПТ-САУ пороги сейчас те же (td/params.py: TD_LOOK_*), поэтому общие.
FULL_ARMOR_RATIO = LOOK_FRONT_RATIO[1]
FULL_GUN_RATIO = LOOK_GUN_RATIO[1]
FULL_SPEED_RATIO = LOOK_SPEED_RATIO[1]

# Эталон «обычной» сборки у каждого типа техники: класс спецификации -> (лоб, калибр) по умолчанию.
# Игрок в базовой сборке любого типа должен получать нулевую угрозу.
_REFS = {t.spec_cls: (t.params["front_armor_mm"].default, t.params["gun_caliber_mm"].default)
         for t in VEHICLE_TYPES.values()}

# Что спавнить против каждой «выкрученной» характеристики игрока.
# Число: насколько растёт множитель шанса при максимальном уровне (отрицательное: шанс падает).
COUNTERS = {
    "armor": {"destroyer": 2.0, "bunker": 1.5, "scout": -0.5, "sniper": 1.5, "assault": -0.3},
    "gun":   {"bunker": 1.5, "universal": 0.5, "assault": 0.5},
    "speed": {"scout": 2.0, "universal": 1.0, "bunker": -0.3, "assault": 0.8, "sniper": -0.3},
}

MIN_MULT = 0.15     # шанс архетипа не падает ниже 15% от обычного
MAX_MULT = 4.0      # и не растёт больше чем в 4 раза

def _reference(spec):
    """(эталонный лоб, эталонный калибр) для типа техники этой спецификации."""
    for cls in type(spec).__mro__:
        ref = _REFS.get(cls)
        if ref is not None:
            return ref
    raise TypeError(f"threat_profile: тип {type(spec).__name__} не зарегистрирован в VEHICLE_TYPES")

def _level(ratio, full):
    """0 на эталоне и ниже, 1 при ratio >= full, между ними линейно."""
    return clamp((ratio - 1.0) / (full - 1.0), 0.0, 1.0)

def threat_profile(spec):
    """Насколько игрок «выкручен» по каждой оси: {"armor": 0..1, "gun": 0..1, "speed": 0..1}.
    Эталоны брони и калибра берутся у типа техники игрока, скорость уже относительна его шасси (q_pw)."""
    ref_front, ref_cal = _reference(spec)
    return {
        "armor": _level(spec.front / ref_front, FULL_ARMOR_RATIO),
        "gun": _level(spec.cal / ref_cal, FULL_GUN_RATIO),
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