"""vehicles/registry.py — реестр типов техники: всё, что нужно конструктору и игре, чтобы создать машину."""
from dataclasses import dataclass
from typing import Callable, Optional

from engine import VehicleKind
from vehicles.chassis.hull_noses import sloped_nose_for_mass
from vehicles.chassis.hulls import NOSE_PIKE
from vehicles.gun.tuning import MBT_GUN, TD_GUN, GunProfile
from .tank import (
    Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS,
    caliber_range_for, estimate_mass, turret_shift_range
)
from .td import (
    TankDestroyer, TDSpec, TDRenderer, TD_PARAMS, TD_DESIGN_PARAMS,
    TD_DESIGN_DEFAULTS, td_caliber_limits, mount_shift_range
)
from .spg import (ArtilleryVehicle, SPGSpec, SPGRenderer, SPG_PARAMS,
                  spg_loadout_cost, spg_extra_values)
from .tank.design import TURRET_DESIGN_DEFAULTS, TURRET_DESIGN_PARAMS

@dataclass(frozen=True)
class VehicleType:
    kind: VehicleKind
    label: str               # подпись кнопки
    params: dict             # описание ползунков
    spec_cls: type
    entity_cls: type
    renderer_cls: type
    gun_profile: GunProfile
    playable: bool = True    # False: тип доступен только ботам
    # Хуки для ai/loadout.py
    extra_values: Optional[Callable] = None   # (values, arch, tune, screen) -> полный словарь сборки
    cost_fn: Optional[Callable] = None        # (values) -> неокруглённая цена
    # Хуки конструктора
    caliber_limits: Optional[Callable] = None  # (values) -> (мин, макс) калибра при текущих броне и мощности
    sloped_nose: Optional[Callable] = None     # (values) -> NOSE_PIKE | NOSE_WEDGE: какой скос положен машине
    # Дизайн техники
    design_defaults: Optional[dict] = None
    # Рамки калибра для ботов
    bot_caliber_limits: Optional[Callable] = None
    # Границы ползунков дизайна
    design_rules: Optional[Callable] = None

# ---------- правила конструктора ----------
def _mbt_caliber_limits(v):
    """ОБТ: допустимый калибр зависит от тяжести корпуса (броня и мощность)."""
    return caliber_range_for(v["front_armor_mm"], v["side_armor_mm"], v["rear_armor_mm"], v["engine_power_hp"])

def _mbt_sloped_nose(v):
    """ОБТ: тяжелее порога массы клин, легче щучий нос."""
    mass = estimate_mass(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                         v["rear_armor_mm"], v["engine_power_hp"], v.get("front_screen_mm", 0.0),
                         gun_length=v.get("gun_length_cal"),
                         turret_size=v.get("turret_size", 1.0))
    return sloped_nose_for_mass(mass)

def _td_sloped_nose(v):
    """ПТ-САУ: только щучий нос."""
    return NOSE_PIKE

def _td_caliber_limits(v):
    """ПТ-САУ: допустимый калибр зависит от брони (см. td/rules.py)."""
    return td_caliber_limits(v["front_armor_mm"], v["side_armor_mm"], v["rear_armor_mm"])

def _mbt_design_rules(v):
    """ОБТ: границы сдвига оси башни зависят от класса корпуса."""
    return {"turret_axis_shift_m": turret_shift_range(v["front_armor_mm"], v["side_armor_mm"],
                                                      v["rear_armor_mm"], v["engine_power_hp"])}

def _td_design_rules(v):
    """ПТ-САУ: границы сдвига орудия зависят от калибра."""
    return {"mount_shift_m": mount_shift_range(v["gun_caliber_mm"])}

# Все параметры дизайна по ключам (нужны сессии, чтобы подрезать загруженные значения)
DESIGN_PARAMS = {**TURRET_DESIGN_PARAMS, **TD_DESIGN_PARAMS}

VEHICLE_TYPES = {
    VehicleKind.MBT: VehicleType(VehicleKind.MBT, "ОБТ", TANK_PARAMS, TankSpec, Tank, TankRenderer, MBT_GUN,
                                 caliber_limits=_mbt_caliber_limits, sloped_nose=_mbt_sloped_nose,
                                 design_defaults=TURRET_DESIGN_DEFAULTS, design_rules=_mbt_design_rules),
    VehicleKind.TD: VehicleType(VehicleKind.TD, "ПТ-САУ", TD_PARAMS, TDSpec, TankDestroyer, TDRenderer, TD_GUN,
                                caliber_limits=_td_caliber_limits, bot_caliber_limits=_td_caliber_limits,
                                sloped_nose=_td_sloped_nose,
                                design_defaults=TD_DESIGN_DEFAULTS, design_rules=_td_design_rules),
    VehicleKind.SPG: VehicleType(VehicleKind.SPG, "САУ", SPG_PARAMS, SPGSpec, ArtilleryVehicle, SPGRenderer,
                                 MBT_GUN, playable=False,
                                 extra_values=spg_extra_values, cost_fn=spg_loadout_cost),
}

# Рендереры по виду техники: производная от реестра, отдельно её вести не нужно.
RENDERERS = {kind: vt.renderer_cls for kind, vt in VEHICLE_TYPES.items()}

# Страховка от рассинхронизации: вид в записи реестра должен совпадать с видом самого класса машины.
for _kind, _vt in VEHICLE_TYPES.items():
    if _vt.entity_cls.kind is not _kind:
        raise ValueError(f"registry: {_vt.entity_cls.__name__}.kind = {_vt.entity_cls.kind}, а запись реестра {_kind}")

def make_vehicle(kind, spec, **kwargs):
    """Создаёт машину нужного типа в точке (0, 0)."""
    return VEHICLE_TYPES[kind].entity_cls(0.0, 0.0, spec=spec, **kwargs)