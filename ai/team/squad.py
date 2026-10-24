"""ai/team/squad.py — общая «доска» ботов: сектора вокруг игрока и тот, на кого смотрит игрок."""
import math

from engine import bearing_deg, clamp, shortest_angle_diff
from ..tactics.cover import attention

SEP_MIN_DEG, SEP_MAX_DEG = 35.0, 90.0     # угловой разнос между соседними ботами

class Squad:
    def __init__(self):
        self.focus = None        # танк бота, на которого сейчас наведена башня игрока (или None)
        self._slot = {}          # id(мозг) -> азимут сектора относительно игрока (система игры)

    def slot(self, brain):
        return self._slot.get(id(brain))

    def update(self, bots, enemy):
        """Раз в кадр до мозгов. Порядок ботов вокруг игрока сохраняется: пересекать друг другу путь не приходится."""
        self._slot = {}
        self.focus = None
        alive = [b for b in bots if b.tank.alive]
        if not alive or not enemy.alive:
            return
        tanks = [b.tank for b in alive]
        for b in alive:
            if attention(enemy, b.tank, tanks) == "me":
                self.focus = b.tank
                break
        n = len(alive)
        if n < 2:
            return
        ang = [bearing_deg(enemy.x, enemy.y, b.tank.x, b.tank.y) for b in alive]
        s = sum(math.sin(math.radians(a)) for a in ang)
        c = sum(math.cos(math.radians(a)) for a in ang)
        center = math.degrees(math.atan2(s, c))            # круговое среднее: откуда группа в целом
        order = sorted(range(n), key=lambda i: shortest_angle_diff(ang[i], center))
        sep = clamp(360.0 / (n + 1), SEP_MIN_DEG, SEP_MAX_DEG)
        for rank, i in enumerate(order):
            self._slot[id(alive[i].brain)] = (center + (rank - (n - 1) / 2.0) * sep) % 360.0