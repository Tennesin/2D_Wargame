"""ai/movement/navigator.py — путь A*: планирование по таймеру, запреты на стены, «плохие места», езда к точке."""
import math

from engine import PX_PER_M, heading_vector, bearing_deg
from .pathfinding import find_path
from ..team.hazards import safe_goal

MIN_REPLAN_S = 0.5           # быстрее этого путь не перестраивается даже при смене цели
REPLAN_S = 1.5               # период перепланирования (с разбросом ±20%)
REPLAN_GOAL_M = 10.0         # цель сместилась больше чем на это
REPLAN_OFFPATH_M = 6.0       # бот ушёл с пути дальше этого
FORBID_WALL_S = 15.0         # сколько секунд «непробиваемой» считается стена, с которой не вышло
STUCK_SPOT_S = 12.0          # сколько секунд помним место, где застряли
BREACH_TRIGGER_M = 25.0      # стена на пути ближе этого: пора решать, ломать ли её
REVERSE_CHECK_M = 5.0        # на сколько метров назад смотрим, прежде чем сдавать задом
STUCK_MARK_AHEAD_M = 4.0     # на сколько метров впереди ставим пометку «здесь застряли»
HAZARD_WAIT_PX = 2.5 * PX_PER_M   # у кромки зоны обстрела ближе этого: стоим и ждём падения
ALLY_PAD_M = 1.5             # запас вокруг корпуса союзника в штрафной зоне
ALLY_PREDICT_S = 1.5         # куда союзник сдвинется за это время (вторая зона штрафа)

class Navigator:
    def __init__(self, rng):
        self.rng = rng
        self._path = None
        self._replan_in = 0.0
        self._plan_age = 0.0                  # сколько секунд текущему пути
        self._forbidden = {}                  # id стены -> секунд до снятия запрета
        self._bad_spots = []                  # [[x, y, ttl], ...] места застревания
        self._hazard_sig = ()                 # какие зоны обстрела учтены в текущем пути

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
        fx, fy = heading_vector(me.hull_angle)
        ahead = STUCK_MARK_AHEAD_M * PX_PER_M
        self._bad_spots.append([me.x + fx * ahead, me.y + fy * ahead, STUCK_SPOT_S])
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

    def _plan(self, me, ctx, goal, no_breach=False, hazards=()):
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
                                   self._forbidden, self._bad_spots, no_breach, hazards,
                                   self._ally_discs(me, ctx))
            self._replan_in = REPLAN_S * self.rng.uniform(0.8, 1.2)
            self._plan_age = 0.0
        return self._path

    @staticmethod
    def _zones(me, ctx):
        board = getattr(ctx, "hazards", None)
        return board.zones(me) if board is not None else ()

    @staticmethod
    def _ally_discs(me, ctx):
        out = []
        pad = ALLY_PAD_M * PX_PER_M
        for b in ctx.fleet.bots:
            t = b.tank
            if t is me or not t.alive:
                continue
            r = t.spec.HULL_REACH_PX + pad
            out.append((t.x, t.y, r))
            vx, vy = t.velocity_px()
            if vx or vy:
                out.append((t.x + vx * ALLY_PREDICT_S, t.y + vy * ALLY_PREDICT_S, r))
        return tuple(out)

    def drive_to(self, me, ctx, goal, want, no_breach=False, on_wall=None):
        """Курс и газ при езде к goal: (курс, газ)."""
        zones = self._zones(me, ctx)
        hard = tuple(z for z in zones if not z.soft)
        sig = tuple(z.key for z in hard)
        if sig != self._hazard_sig:                               # появилась или упала зона: путь устарел
            self._hazard_sig = sig
            self.invalidate()
        if zones:
            goal, waiting = safe_goal(me, goal, zones)
            if waiting and math.hypot(goal[0] - me.x, goal[1] - me.y) < HAZARD_WAIT_PX:
                return want, 0.0                                  # дошли до кромки: стоим лицом к врагу

        for _ in range(2):              # второй проход нужен после запрета непробиваемой стены
            path = self._plan(me, ctx, goal, no_breach, hard)
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