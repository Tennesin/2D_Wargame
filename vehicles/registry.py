"""vehicles/registry.py — реестр типов техники: всё, что нужно конструктору и игре, чтобы создать машину."""
from dataclasses import dataclass
from typing import Callable, Optional

from engine import VehicleKind
from vehicles.chassis.hull_noses import sloped_nose_for_mass
from vehicles.chassis.hulls import NOSE_PIKE
from vehicles.gun.tuning import MBT_GUN, TD_GUN, GunProfile
from .tank import Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS, caliber_range_for, estimate_mass
from .td import TankDestroyer, TDSpec, TDRenderer, TD_PARAMS
from .spg import (ArtilleryVehicle, SPGSpec, SPGRenderer, SPG_PARAMS,
                  spg_loadout_cost, spg_extra_values)

@dataclass(frozen=True)
class VehicleType:
    kind: VehicleKind
    label: str               # подпись кнопки
    params: dict             # описание ползунков
    spec_cls: type
    entity_cls: type
    renderer_cls: type
    gun_profile: GunProfile
    playable: bool = True    # False: тип доступен только ботам (нет в конструкторе и сессии)
    # Хуки для ai/loadout.py. None = обычная техника с настраиваемым орудием (урон, пробитие, нос, экраны).
    extra_values: Optional[Callable] = None   # (values, arch, tune, screen) -> полный словарь сборки
    cost_fn: Optional[Callable] = None        # (values) -> неокруглённая цена
    # Хуки конструктора. None = у этого типа такого правила нет.
    caliber_limits: Optional[Callable] = None  # (values) -> (мин, макс) калибра при текущих броне и мощности
    sloped_nose: Optional[Callable] = None     # (values) -> NOSE_PIKE | NOSE_WEDGE: какой скос положен машине

# ---------- правила конструктора ----------
def _mbt_caliber_limits(v):
    """ОБТ: допустимый калибр зависит от тяжести корпуса (броня и мощность)."""
    return caliber_range_for(v["front_armor_mm"], v["side_armor_mm"], v["rear_armor_mm"], v["engine_power_hp"])

def _mbt_sloped_nose(v):
    """ОБТ: тяжелее порога массы клин, легче щучий нос."""
    mass = estimate_mass(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                         v["rear_armor_mm"], v["engine_power_hp"], v.get("front_screen_mm", 0.0),
                         gun_length=v.get("gun_length_cal"))
    return sloped_nose_for_mass(mass)

def _td_sloped_nose(v):
    """ПТ-САУ: только щучий нос."""
    return NOSE_PIKE

VEHICLE_TYPES = {
    VehicleKind.MBT: VehicleType(VehicleKind.MBT, "ОБТ", TANK_PARAMS, TankSpec, Tank, TankRenderer, MBT_GUN,
                                 caliber_limits=_mbt_caliber_limits, sloped_nose=_mbt_sloped_nose),
    VehicleKind.TD: VehicleType(VehicleKind.TD, "ПТ-САУ", TD_PARAMS, TDSpec, TankDestroyer, TDRenderer, TD_GUN,
                                sloped_nose=_td_sloped_nose),
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