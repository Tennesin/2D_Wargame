"""game/fleet.py — все танки на карте: игрок и боты."""

class Fleet:
    def __init__(self, player):
        self.player = player
        self.bots = []                      # список ai.Bot

    @property
    def tanks(self):
        """Сначала боты, потом игрок (игрок рисуется сверху)."""
        return [b.tank for b in self.bots] + [self.player]

    def remove_dead(self):
        """Убирает уничтоженных ботов, возвращает сколько убрано. Игрок остаётся всегда."""
        before = len(self.bots)
        self.bots = [b for b in self.bots if b.tank.alive]
        return before - len(self.bots)

    def obbs_near(self, me, radius):
        """Прямоугольники (корпус, ствол) чужих танков рядом с me: это препятствия для me."""
        result = []
        for t in self.tanks:
            if t is me or not t.alive:
                continue
            reach = radius + t.reach_px()
            dx, dy = t.x - me.x, t.y - me.y
            if dx * dx + dy * dy <= reach * reach:
                result.extend(t.footprint_at(t.x, t.y, t.hull_angle))
        return result

    def blocks_obb(self, obb):
        """Задевает ли прямоугольник хоть один живой танк (для SpawnFinder и WallEditor)."""
        return any(t.hits_obb(obb) for t in self.tanks if t.alive)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Источник для TargetSet. Танки той же команды, что и стрелок, снаряд не задевает."""
        team = getattr(ignore, "team", None)
        best = None
        for t in self.tanks:
            if not t.alive or t is ignore or (team is not None and t.team == team):
                continue
            res = t.raycast(x0, y0, x1, y1)
            if res is not None and (best is None or res[1] < best[1]):
                best = res
        return best