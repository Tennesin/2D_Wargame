"""game/fleet.py — вся техника на карте: игрок и боты."""

class Fleet:
    def __init__(self, player):
        self.player = player                # любая Vehicle
        self.bots = []                      # список ai.Bot
        self.kills = 0                      # сколько ботов уничтожено за партию

    @property
    def vehicles(self):
        """Сначала боты, потом игрок (игрок рисуется сверху)."""
        return [b.tank for b in self.bots] + [self.player]

    def remove_dead(self):
        """Убирает уничтоженных ботов, учитывает их в kills и возвращает сколько убрано.
        Игрок остаётся всегда."""
        before = len(self.bots)
        self.bots = [b for b in self.bots if b.tank.alive]
        removed = before - len(self.bots)
        self.kills += removed
        return removed

    def obbs_near(self, me, radius):
        """Прямоугольники чужой техники рядом с me: это препятствия для me."""
        result = []
        for t in self.vehicles:
            if t is me or not t.alive:
                continue
            reach = radius + t.reach_px()
            dx, dy = t.x - me.x, t.y - me.y
            if dx * dx + dy * dy <= reach * reach:
                result.extend(t.footprint_at(t.x, t.y, t.hull_angle))
        return result

    def blocks_obb(self, obb):
        """Задевает ли прямоугольник хоть одну живую машину (для SpawnFinder и WallEditor)."""
        return any(t.hits_obb(obb) for t in self.vehicles if t.alive)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Источник для TargetSet. Машины той же команды, что и стрелок, снаряд не задевает."""
        team = getattr(ignore, "team", None)
        best = None
        for t in self.vehicles:
            if not t.alive or t is ignore or (team is not None and t.team == team):
                continue
            res = t.raycast(x0, y0, x1, y1)
            if res is not None and (best is None or res[1] < best[1]):
                best = res
        return best