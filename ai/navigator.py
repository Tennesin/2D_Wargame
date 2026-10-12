"""ai/navigator.py — путь A*: планирование по таймеру, запреты на стены, «плохие места», езда к точке."""
import math

from engine import PX_PER_M, heading_vector, bearing_deg
from .pathfinding import find_path

MIN_REPLAN_S = 0.5           # быстрее этого путь не перестраивается даже при смене цели
REPLAN_S = 1.5               # период перепланирования (с разбросом ±20%)
REPLAN_GOAL_M = 10.0         # цель сместилась больше чем на это
REPLAN_OFFPATH_M = 6.0       # бот ушёл с пути дальше этого
FORBID_WALL_S = 15.0         # сколько секунд «непробиваемой» считается стена, с которой не вышло
STUCK_SPOT_S = 12.0          # сколько секунд помним место, где застряли
BREACH_TRIGGER_M = 25.0      # стена на пути ближе этого: пора решать, ломать ли её
REVERSE_CHECK_M = 5.0        # на сколько метров назад смотрим, прежде чем сдавать задом

class Navigator:
    def __init__(self, rng):
        self.rng = rng
        self._path = None
        self._replan_in = 0.0
        self._plan_age = 0.0                  # сколько секунд текущему пути
        self._forbidden = {}                  # id стены -> секунд до снятия запрета
        self._bad_spots = []                  # [[x, y, ttl], ...] места застревания

    def tick(self, dt):
        """Таймеры пути и забывание запретов и плохих мест."""
        self._replan_in -= dt
        self._plan_age += dt
        if self._forbidden:
            self._forbidden = {k: t - dt for k, t in self._forbidden.items() if t - dt > 0.0}
        if self._bad_spots:
            for s in self._bad_spots:
                s[2] -= dt
            self._bad_spots[:] = [s for s in self._bad_spots if s[2] > 0.0]

    def invalidate(self):
        """Путь устарел: перестроить при ближайшей возможности."""
        self._path = None
        self._replan_in = 0.0

    def remember_stuck(self, me):
        """Бот застрял: помечаем место впереди штрафом и перестраиваем путь."""
        fx, fy = heading_vector(me.hull_angle)
        self._bad_spots.append([me.x + fx * 400.0, me.y + fy * 400.0, STUCK_SPOT_S])
        self.invalidate()

    @staticmethod
    def rear_blocked(me, ctx):
        """Занято ли место позади корпуса (камень, глубокая вода, стена, край мира) на пути заднего хода."""
        fx, fy = heading_vector(me.hull_angle)
        dist = REVERSE_CHECK_M * PX_PER_M
        for k in (0.5, 1.0):
            hull = me.footprint_at(me.x - fx * dist * k, me.y - fy * dist * k, me.hull_angle)[0]
            if ctx.terrain.blocks_obb(hull) or ctx.walls.blocks_obb(hull):
                return True
        return False

    def _plan(self, me, ctx, goal, no_breach=False):
        """Текущий путь; перестраивается по таймеру, при смене цели, при уходе с пути и по прибытии.
        Если лимит построений на этот кадр выбран, возвращается прежний путь (или None)."""
        p = self._path
        need = self._replan_in <= 0.0
        if p is not None and not need and self._plan_age >= MIN_REPLAN_S:
            need = (math.hypot(goal[0] - p.goal[0], goal[1] - p.goal[1]) > REPLAN_GOAL_M * PX_PER_M
                    or p.deviation_px(me.x, me.y) > REPLAN_OFFPATH_M * PX_PER_M
                    or p.done(me.x, me.y))
        if need:
            if not ctx.budget.try_take():
                return p                                          # повторим при следующем «размышлении»
            self._path = find_path(me, goal, ctx.walls, ctx.nav,
                                   self._forbidden, self._bad_spots, no_breach)
            self._replan_in = REPLAN_S * self.rng.uniform(0.8, 1.2)
            self._plan_age = 0.0
        return self._path

    def drive_to(self, me, ctx, goal, want, no_breach=False, on_wall=None):
        """Курс и газ при езде к goal: (курс, газ).
        Если на пути близко стена, вызывается on_wall(wall): True значит «прорыв начат», и тогда
        возвращается None (управление взял прорыв). Иначе стена считается глухой на FORBID_WALL_S.
        Нет пути: стоим и поворачиваемся к want."""
        for _ in range(2):              # второй проход нужен после запрета непробиваемой стены
            path = self._plan(me, ctx, goal, no_breach)
            if path is None:
                break
            wall = path.breach_wall
            to_wall = (math.hypot(wall.x - me.x, wall.y - me.y) - wall.radius_px
                       if wall is not None else None)
            if wall is None or to_wall > BREACH_TRIGGER_M * PX_PER_M:
                return bearing_deg(me.x, me.y, *path.next_point(me.x, me.y)), 1.0
            if on_wall is not None and on_wall(wall):
                return None
            self._forbidden[id(wall)] = FORBID_WALL_S             # с этого угла не выходит: считаем стену глухой
            self.invalidate()
        return want, 0.0