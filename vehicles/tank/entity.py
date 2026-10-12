"""tank/entity.py — танк: башня и орудие поверх общего шасси Vehicle (vehicles/base.py)."""
import math

from engine import shortest_angle_diff, Shot, heading_vector, bearing_deg, fmt_num, Team
from ..base import Vehicle

class Tank(Vehicle):
    renderer_key = "tank"
    AIM_DEAD_ZONE = 100.0  # если курсор ближе к центру танка (1 м), башня не дёргается

    def __init__(self, x=0.0, y=0.0, *, spec, team_color=(200, 40, 40),
                 team=Team.PLAYER, label="танк"):
        super().__init__(x, y, spec=spec, team_color=team_color, team=team, label=label)
        self.turret_rel_angle = 0.0     # угол башни ОТНОСИТЕЛЬНО корпуса
        self.turret_rate = 0.0          # текущая угловая скорость башни относительно корпуса, °/с
        self.reload_left = 0.0          # сколько секунд осталось до следующего выстрела
        self.since_shot = 999.0         # сколько секунд прошло с последнего выстрела (для отката)

    @property
    def turret_angle(self):
        """Абсолютный угол башни = корпус + относительный угол."""
        return (self.hull_angle + self.turret_rel_angle) % 360.0

    def place_at(self, spot):
        super().place_at(spot)
        self.turret_rate = 0.0

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

    # ---------- оружие ----------
    def _update_weapons(self, command, dt):
        self._aim_turret(command.aim_point, dt)
        return self._update_gun(command.fire, dt)      # Shot или None

    def _aim_turret(self, aim_point, dt):
        s = self.spec
        target_rate = 0.0
        diff = 0.0
        if aim_point is not None:
            dx = aim_point[0] - self.x
            dy = aim_point[1] - self.y
            if math.hypot(dx, dy) >= self.AIM_DEAD_ZONE:
                target_abs = bearing_deg(self.x, self.y, *aim_point)
                diff = shortest_angle_diff(target_abs, self.turret_angle)
                # скорость, с которой ещё успеем затормозить к цели: v = sqrt(2·α·путь)
                allowed = math.sqrt(2.0 * s.turret_alpha * abs(diff))
                target_rate = math.copysign(min(s.turret_turn, allowed), diff)

        # цели нет (Q, курсор над интерфейсом) — башня плавно останавливается по инерции
        self.turret_rate = self._approach(self.turret_rate, target_rate,
                                          s.turret_alpha, s.turret_alpha, dt)
        delta = self.turret_rate * dt
        if diff != 0.0 and delta * diff > 0.0 and abs(delta) > abs(diff):
            delta = diff                                  # не перелетаем цель
            self.turret_rate = 0.0

        self.turret_rel_angle = (self.turret_rel_angle + delta) % 360.0

    def _update_gun(self, fire, dt):
        """Перезарядка и выстрел. Возвращает Shot, если выстрел произошёл в этом кадре."""
        self.reload_left = max(0.0, self.reload_left - dt)
        self.since_shot += dt
        if not fire or self.reload_left > 0.0:
            return None

        self.reload_left = self.spec.reload
        self.since_shot = 0.0
        mx, my = self.muzzle_point()
        return Shot(mx, my, self.turret_angle)

    def muzzle_point(self):
        """Текущая позиция дульного среза (мировые px)."""
        fx, fy = heading_vector(self.turret_angle)
        dist = self.spec.MUZZLE_DIST_PX
        return self.x + fx * dist, self.y + fy * dist

    @property
    def recoil_m(self):
        """Насколько ствол сейчас утоплен в башню (метры эталонного спрайта)."""
        T = self.spec.RECOIL_TIME
        if self.since_shot >= T:
            return 0.0
        k = self.since_shot / T
        depth = self.spec.RECOIL_DEPTH_M
        if k < 0.2:                                   # быстрый откат назад (первые 20% времени)
            return depth * (k / 0.2)
        return depth * (1.0 - (k - 0.2) / 0.8) ** 2   # плавный накат обратно