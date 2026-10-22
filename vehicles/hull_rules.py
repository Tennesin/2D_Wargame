"""vehicles/tank/hull_rules.py — правила корпуса ОБТ по ползункам: класс корпуса (лёгкий/средний/тяжёлый),
положение оси башни и допустимый калибр. У ПТ-САУ и будущей техники свои правила."""
from engine import clamp, lerp, round_to
from .gun_params import CALIBER
from .hulls import HullClass, LIGHT_LAYOUT, HEAVY_LAYOUT

# ==========================================
# КЛАССИФИКАЦИЯ ПО ПОЛЗУНКАМ
# ==========================================
CLASS_W_ARMOR = 1.0
CLASS_W_POWER = 0.5
CLASS_LIGHT_BELOW = -0.20      # индекс ниже этого: лёгкий
CLASS_HEAVY_ABOVE = 0.15       # выше этого: тяжёлый (стартовые значения, подгоняются по отладке)
CLASS_BORDER_EPS = 0.03        # «рядом с порогом»: ещё чуть-чуть, и силуэт сменится

TURRET_AXIS_FRONT_M = 0.3      # ось башни у эталона (минус = позади центра корпуса)
TURRET_AXIS_REAR_M = -0.5      # самое заднее положение
TURRET_AXIS_STEP_M = 0.1       # квантование: ограничивает число вариантов спрайта
TURRET_SHIFT_FROM = -0.05      # индекс, с которого башня начинает уезжать назад (эталон ≈ -0.09 стоит на месте)
TURRET_SHIFT_TO = 0.45         # индекс, на котором башня уже в крайнем заднем положении

HEAVY_ENABLED = True          # True вернёт тяжёлый корпус (скачок формы при индексе > CLASS_HEAVY_ABOVE)

def near_class_border(index):
    """Индекс в пределах CLASS_BORDER_EPS от порога смены класса."""
    dist = abs(index - CLASS_LIGHT_BELOW)
    if HEAVY_ENABLED:
        dist = min(dist, abs(index - CLASS_HEAVY_ABOVE))
    return dist <= CLASS_BORDER_EPS

def class_index(armor_t, power_t):
    """Индекс «тяжести»: много брони и мало мощности = больше."""
    return CLASS_W_ARMOR * armor_t - CLASS_W_POWER * power_t

def class_for_index(index):
    if index < CLASS_LIGHT_BELOW:
        return HullClass.LIGHT
    if HEAVY_ENABLED and index > CLASS_HEAVY_ABOVE:
        return HullClass.HEAVY
    return HullClass.MEDIUM

def classify(armor_t, power_t):
    """Класс корпуса по нормированным броне и мощности (обе 0..1)."""
    return class_for_index(class_index(armor_t, power_t))

def turret_axis_for(cls, index):
    """Ось башни вдоль корпуса, м (плюс = впереди центра корпуса). Чем тяжелее индекс, тем дальше назад.
    У лёгкого корпуса башня всегда по центру."""
    if cls is HullClass.LIGHT:
        return LIGHT_LAYOUT.axis_fwd_m
    if cls is HullClass.HEAVY:
        return HEAVY_LAYOUT.axis_fwd_m
    t = clamp((index - TURRET_SHIFT_FROM) / (TURRET_SHIFT_TO - TURRET_SHIFT_FROM), 0.0, 1.0)
    axis = round_to(lerp(TURRET_AXIS_FRONT_M, TURRET_AXIS_REAR_M, t), TURRET_AXIS_STEP_M)
    return round(axis, 3) + 0.0                      # + 0.0 убирает «-0.0»

# ==========================================
# ОГРАНИЧЕНИЕ КАЛИБРА ПО ТЯЖЕСТИ КОРПУСА
# ==========================================
CAL_INDEX_FROM = -0.40         # индекс «тяжести», при котором корпус считается самым лёгким
CAL_INDEX_TO = 0.40            # и самым тяжёлым (дальше значения не меняются)
CAL_MIN_AT_LIGHT = CALIBER.min     # самый лёгкий корпус: калибр от этого
CAL_MAX_AT_LIGHT = 105.0           # ... до этого
CAL_MIN_AT_HEAVY = 105.0           # самый тяжёлый корпус: калибр от этого
CAL_MAX_AT_HEAVY = CALIBER.max     # ... до этого

def caliber_limits(index):
    """(мин, макс) калибра, мм, для корпуса с индексом тяжести index. Работает и при HEAVY_ENABLED = False."""
    t = clamp((index - CAL_INDEX_FROM) / (CAL_INDEX_TO - CAL_INDEX_FROM), 0.0, 1.0)
    return (round(lerp(CAL_MIN_AT_LIGHT, CAL_MIN_AT_HEAVY, t)),
            round(lerp(CAL_MAX_AT_LIGHT, CAL_MAX_AT_HEAVY, t)))