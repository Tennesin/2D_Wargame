"""td/layout.py — раскладка корпуса ПТ-САУ. Корпус и гусеницы как у среднего класса,
свои: контур, лобовая плита, палуба и люк. Сдвиг оси орудия зависит от калибра."""
from dataclasses import replace
from functools import lru_cache

from vehicles.chassis.hulls import MEDIUM_LAYOUT, with_box_hitbox, NOSE_FLAT
from vehicles.chassis.hull_noses import layout_with_nose
from .params import TD_HULL_COLL_HALF_W_M, TD_HULL_COLL_HALF_L_M, TD_HULL_HALF_M

TD_LAYOUT = with_box_hitbox(
    MEDIUM_LAYOUT, TD_HULL_COLL_HALF_W_M, TD_HULL_COLL_HALF_L_M,
    key="td",
    outline=((-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (1.35, 2.65),
             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.3)),
    front_plate=((-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (-1.35, -2.3)),
    deck_rect=(-1.25, -2.25, 2.50, 4.60),
    hatch=(0.78, -2.52, 0.20),                  # люк механика на лбу
    canvas_half_m=TD_HULL_HALF_M,               # холст рассчитан на любой сдвиг оси орудия
    scale_range=(0.5, 2.0), scale_step=0.0,     # HULL_SCALE == size_k: TURRET_SCALE у ПТ-САУ равен size_k
)

@lru_cache(maxsize=None)
def td_layout(mount_fwd_m, nose=NOSE_FLAT):
    """Раскладка ПТ-САУ с осью орудия на mount_fwd_m метров впереди центра корпуса
    и выбранным носом (значений мало: MOUNT_FWD_M квантуется шагом 0.1 м)."""
    base = replace(TD_LAYOUT, key=f"td{mount_fwd_m:+.1f}", axis_fwd_m=mount_fwd_m)
    return layout_with_nose(base, nose)