"""td/entity.py — ПТ-САУ: орудие в лафете с ограниченным сектором наводки."""
from engine import fmt_num, Team
from ..gun_vehicle import GunVehicle

class TankDestroyer(GunVehicle):
    renderer_key = "td"

    def __init__(self, x=0.0, y=0.0, *, label="ПТ-САУ", **kwargs):
        super().__init__(x, y, label=label, **kwargs)

    def describe(self):
        s = self.spec
        title = "Ваша ПТ-САУ" if self.team is Team.PLAYER else f"Враг: {self.label}"
        return title, [
            ("Калибр", f"{s.cal:.0f} мм"),
            ("УГН", f"±{s.TURRET_ARC_DEG / 2.0:.0f} °"),
            ("Броня: лоб", f"{s.front:.0f} мм"),
            ("Броня: борт", f"{s.side:.0f} мм"),
            ("Броня: корма", f"{s.rear:.0f} мм"),
            ("Масса", f"{fmt_num(s.mass, 1)} т"),
        ]