"""tank/entity.py — танк: башня и орудие живут в GunVehicle, здесь только то, что отличает ОБТ."""
from engine import fmt_num, Team
from ..gun_vehicle import GunVehicle

class Tank(GunVehicle):
    renderer_key = "tank"

    def __init__(self, x=0.0, y=0.0, *, label="танк", **kwargs):
        super().__init__(x, y, label=label, **kwargs)

    def describe(self):
        """(заголовок, [(название, значение), ...]) для краткой сводки."""
        s = self.spec
        title = "Ваш танк" if self.team is Team.PLAYER else f"Враг: {self.label}"
        return title, [
            ("Калибр", f"{s.cal:.0f} мм"),
            ("Броня: лоб", f"{s.front:.0f} мм"),
            ("Броня: борт", f"{s.side:.0f} мм"),
            ("Броня: корма", f"{s.rear:.0f} мм"),
            ("Масса", f"{fmt_num(s.mass, 1)} т"),
        ]