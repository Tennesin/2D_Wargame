"""vehicles/tank/entity.py — танк: башня и орудие живут в GunVehicle, здесь только то, что отличает ОБТ."""
from vehicles.gun.vehicle import GunVehicle

class Tank(GunVehicle):
    renderer_key = "tank"
    PLAYER_TITLE = "Ваш танк"

    def __init__(self, x=0.0, y=0.0, *, label="танк", **kwargs):
        super().__init__(x, y, label=label, **kwargs)