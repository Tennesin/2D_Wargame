"""vehicles/registry.py — реестр типов техники: всё, что нужно конструктору и игре, чтобы создать машину."""
from dataclasses import dataclass

from engine import VehicleKind
from vehicles.gun.tuning import MBT_GUN, TD_GUN, GunProfile
from .tank import Tank, TankSpec, TankRenderer, PARAMS as TANK_PARAMS
from .td import TankDestroyer, TDSpec, TDRenderer, TD_PARAMS

@dataclass(frozen=True)
class VehicleType:
    kind: VehicleKind
    label: str               # подпись кнопки
    params: dict             # описание ползунков
    spec_cls: type
    entity_cls: type
    renderer_key: str
    gun_profile: GunProfile

VEHICLE_TYPES = {
    VehicleKind.MBT: VehicleType(VehicleKind.MBT, "ОБТ", TANK_PARAMS, TankSpec, Tank, "tank", MBT_GUN),
    VehicleKind.TD: VehicleType(VehicleKind.TD, "ПТ-САУ", TD_PARAMS, TDSpec, TankDestroyer, "td", TD_GUN),
}

RENDERERS = {"tank": TankRenderer, "td": TDRenderer}      # ключ -> класс (экземпляры создаёт тот, кому нужны)

def make_vehicle(kind, spec, **kwargs):
    """Создаёт машину нужного типа в точке (0, 0)."""
    return VEHICLE_TYPES[kind].entity_cls(0.0, 0.0, spec=spec, **kwargs)