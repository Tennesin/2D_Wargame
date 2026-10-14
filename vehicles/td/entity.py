"""td/entity.py — ПТ-САУ: орудие в лафете с ограниченным сектором наводки."""
from ..gun_vehicle import GunVehicle

class TankDestroyer(GunVehicle):
    renderer_key = "td"
    PLAYER_TITLE = "Ваша ПТ-САУ"

    def __init__(self, x=0.0, y=0.0, *, label="ПТ-САУ", **kwargs):
        super().__init__(x, y, label=label, **kwargs)

    def _extra_rows(self):
        return [("УГН", f"±{self.spec.TURRET_ARC_DEG / 2.0:.0f} °")]