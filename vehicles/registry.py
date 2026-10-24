"""vehicles/registry.py — реестр типов техники: всё, что нужно конструктору и игре, чтобы создать машину."""
from dataclasses import dataclass
from typing import Callable, Optional

from engine import VehicleKind
from vehicles.gun.tuning import MBT_GUN, TD_GUN, GunProfile
from .tank import Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS
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
    renderer_key: str
    gun_profile: GunProfile
    playable: bool = True    # False: тип доступен только ботам (нет в конструкторе и сессии)
    # Хуки для ai/loadout.py. None = обычная техника с настраиваемым орудием (урон, пробитие, нос, экраны).
    extra_values: Optional[Callable] = None   # (values, arch, tune, screen) -> полный словарь сборки
    cost_fn: Optional[Callable] = None        # (values) -> неокруглённая цена

VEHICLE_TYPES = {
    VehicleKind.MBT: VehicleType(VehicleKind.MBT, "ОБТ", TANK_PARAMS, TankSpec, Tank, "tank", MBT_GUN),
    VehicleKind.TD: VehicleType(VehicleKind.TD, "ПТ-САУ", TD_PARAMS, TDSpec, TankDestroyer, "td", TD_GUN),
    VehicleKind.SPG: VehicleType(VehicleKind.SPG, "САУ", SPG_PARAMS, SPGSpec, ArtilleryVehicle, "spg",
                                 MBT_GUN, playable=False,
                                 extra_values=spg_extra_values, cost_fn=spg_loadout_cost),
}

RENDERERS = {"tank": TankRenderer, "td": TDRenderer, "spg": SPGRenderer}      # ключ -> класс

def make_vehicle(kind, spec, **kwargs):
    """Создаёт машину нужного типа в точке (0, 0)."""
    return VEHICLE_TYPES[kind].entity_cls(0.0, 0.0, spec=spec, **kwargs)