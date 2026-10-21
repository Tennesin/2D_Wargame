"""engine/palette.py — общие цвета и прозрачность."""
from .kinds import AmmoKind

CONCRETE_SIDE = (92, 92, 96)    # боковая грань бетона и камня
OUTLINE_DARK = (40, 40, 44)     # тёмный контур стен и камней
SHADOW_ALPHA = 80               # прозрачность теней (танк, стены)

# цвета снарядов: (основной, блик, наконечник). Их берут и трассер, и иконки кнопок
AMMO_COLORS = {
    AmmoKind.AP:   ((205, 160, 105), (234, 202, 154), (150, 108, 64)),
    AmmoKind.HEAT: ((110, 175, 225), (205, 235, 255), (60, 105, 160)),
    AmmoKind.HESH: ((196, 190, 80), (238, 232, 150), (128, 120, 44)),
    AmmoKind.HE:   ((225, 110, 70),  (255, 200, 150), (150, 60, 40)),
}

COLOR_GOOD = (90, 200, 90)
COLOR_WARN = (230, 200, 70)
COLOR_BAD = (230, 80, 70)

def hp_color(frac):
    """Цвет полоски здоровья по доле 0..1: общее правило для HUD и указателей ботов."""
    if frac > 0.6:
        return COLOR_GOOD
    if frac > 0.3:
        return COLOR_WARN
    return COLOR_BAD