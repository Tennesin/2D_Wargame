"""td — ПТ-САУ. Снаружи импортируем через пакет vehicles."""
from .params import TD_PARAMS, gun_arc_deg, TD_DESIGN_PARAMS, TD_DESIGN_DEFAULTS
from .rules import td_caliber_limits
from .spec import TDSpec, mount_shift_range
from .entity import TankDestroyer
from .sprites import TDRenderer

__all__ = ["TD_PARAMS", "gun_arc_deg", "TD_DESIGN_PARAMS", "TD_DESIGN_DEFAULTS",
           "td_caliber_limits", "TDSpec", "mount_shift_range", "TankDestroyer", "TDRenderer"]