"""vehicles/tank/design.py — параметры дизайна башни ОБТ: формы, ползунки, значения по умолчанию."""
from engine import Param, round_to

TURRET_STYLES = ("auto", "hex", "oval", "slab")
TURRET_STYLE_RU = {"auto": "Авто", "hex": "Гекс", "oval": "Овал", "slab": "Плита"}

TURRET_DESIGN_PARAMS = {
    "turret_size":         Param("Размер башни",       "×", 0.8, 1.2, 1.0, 0.05, 2),
    "turret_axis_shift_m": Param("Сдвиг оси башни",    "м", -0.6, 0.6, 0.0, 0.1, 1),
}

# Что лежит в session.values у ОБТ по умолчанию
TURRET_DESIGN_DEFAULTS = {"turret_style": "auto", "turret_size": 1.0, "turret_axis_shift_m": 0.0}

def fit_turret_style(value):
    return value if value in TURRET_STYLES else "auto"

def fit_turret_size(value):
    """Размер башни: в границах ползунка и квантованный (число вариантов спрайтов ограничено)."""
    p = TURRET_DESIGN_PARAMS["turret_size"]
    return round(round_to(p.fit(value), p.step), 3)