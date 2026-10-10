"""ai/brain.py — мозг бота: намерение, движение, решение о выстреле."""
import math
from enum import Enum, auto

from engine import VehicleCommand, shortest_angle_diff, PX_PER_M, heading_vector
from combat import compute_aim
from .steering import bearing_deg, steer_to, pick_heading, StuckGuard
from .gunnery import lead_point, damage_by_aspect, flank_point, seconds_to_break

# Флаги для поэтапной проверки: False = бот стоит / не стреляет
AI_MOVE_ENABLED = True
AI_FIRE_ENABLED = True

class Intent(Enum):
    ADVANCE = auto()
    ENGAGE = auto()
    FLANK = auto()
    BREACH = auto()      # ломать стену, которая мешает

BREACH_MAX_S = 25.0          # дольше этого стену не долбим
BREACH_RANGE_M = 14.0        # с какого расстояния стреляем по стене
BREACH_LOOK_M = 30.0         # как далеко вперёд ищем мешающую стену
BREACH_DETOUR_DEG = 50.0     # объезд круче этого угла считается плохим: лучше ломать

FIRE_TOLERANCE_DEG = 2.0
MIN_USEFUL_DAMAGE = 0.15      # меньше этой доли урона по цели бот не стреляет

class BotBrain:
    def __init__(self, arch, skill, rng):
        self.arch, self.skill, self.rng = arch, skill, rng
        self.intent = Intent.ADVANCE
        self.stuck = StuckGuard()
        self._hold = 0.0                                          # сколько ещё держим намерение
        self._think_in = rng.uniform(0.0, 1.0 / skill.think_hz)   # сдвиг фаз между ботами
        self._heading, self._go = 0.0, 0.0                        # результат последнего «размышления»
        self._flank_side = rng.choice((-1, 1))
        self._avoid_side = rng.choice((-1, 1))
        self._react_left = None                                   # None: чистой линии огня нет
        self._breach_wall = None
        self._breach_point = (0.0, 0.0)
        self._breach_left = 0.0

    def think(self, dt, me, enemy, ctx):
        """ctx — объект с полями targets (TargetSet), terrain, walls."""
        if not enemy.alive:
            return VehicleCommand()

        self._hold -= dt
        self._think_in -= dt
        if self.intent is Intent.BREACH:
            self._breach_left -= dt
        if self._think_in <= 0.0:                                 # редко: решения и проверки местности
            self._think_in += 1.0 / self.skill.think_hz
            self._decide(me, enemy, ctx)

        if self.intent is Intent.BREACH:
            aim = self._breach_point
        else:
            aim = lead_point(me, enemy, self.skill.lead_k)        # каждый кадр: дёшево

        throttle, steer = steer_to(me, self._heading, self._go)
        if self.stuck.update(dt, me, throttle != 0.0, self.rng):
            throttle, steer = -1.0, self.stuck.turn
        if not AI_MOVE_ENABLED:
            throttle, steer = 0.0, 0.0

        fire = self._gunnery(dt, me, enemy, ctx, aim) and AI_FIRE_ENABLED
        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim, fire=fire)

    # ---------- решение ----------
    def _decide(self, me, enemy, ctx):
        dist = math.hypot(enemy.x - me.x, enemy.y - me.y)
        engage = self.arch.engage_dist_m * PX_PER_M

        if self.intent is Intent.BREACH:                          # идёт прорыв
            wall = self._breach_wall
            if wall is None or not wall.alive or self._breach_left <= 0.0:
                self._stop_breach()                               # стена рухнула или время вышло
            else:
                self._heading, self._go = self._breach_move(me)
                return

        if self._hold <= 0.0:
            self.intent = self._choose(me, enemy, dist, engage)
            self._hold = 1.5 + self.rng.random()                  # гистерезис

        if self.intent is Intent.FLANK:
            fx, fy = flank_point(enemy, engage, self._flank_side)
            want, go = bearing_deg(me.x, me.y, fx, fy), 1.0
        else:
            want = bearing_deg(me.x, me.y, enemy.x, enemy.y)
            if self.intent is Intent.ENGAGE:
                go = 1.0 if dist > engage * 1.15 else (-1.0 if dist < engage * 0.6 else 0.0)
            else:
                go = 1.0

        look = min(dist, BREACH_LOOK_M * PX_PER_M)
        if go > 0.0:                                              # «щупальца» только при езде вперёд
            heading = pick_heading(me, ctx.terrain, ctx.walls, want, 1000.0, self._avoid_side)
            detour = 180.0 if heading is None else abs(shortest_angle_diff(heading, want))
            if detour >= BREACH_DETOUR_DEG and self._try_breach(me, ctx, want, look):
                return                                            # объезд плох: ломаем стену
            if heading is None:                                   # всё занято: разворот на месте
                self._avoid_side = -self._avoid_side
                heading, go = want + 90.0 * self._avoid_side, 0.0
            want = heading
        elif go == 0.0 and self.intent is Intent.ENGAGE:          # стоим на позиции, но линию огня закрыла стена
            if self._try_breach(me, ctx, want, dist):
                return
        self._heading, self._go = want, go

    def _try_breach(self, me, ctx, bearing, look_px):
        """Есть ли по курсу bearing стена, которую выгодно ломать. Если да, переходим в BREACH."""
        fx, fy = heading_vector(bearing)
        tx, ty = me.x + fx * look_px, me.y + fy * look_px
        hit = ctx.walls.raycast(me.x, me.y, tx, ty)
        if hit is None:
            return False
        wall, t, normal = hit
        cos_i = 1.0 if normal is None else abs(fx * normal[0] + fy * normal[1])
        secs = seconds_to_break(me, wall, cos_i, normal, MIN_USEFUL_DAMAGE)
        if secs is None or secs > BREACH_MAX_S:
            return False                                          # не пробить или слишком долго

        self.intent = Intent.BREACH
        self._breach_wall = wall
        self._breach_point = (me.x + (tx - me.x) * t, me.y + (ty - me.y) * t)
        self._breach_left = secs + 6.0                            # запас на доводку и рикошеты
        self._hold = 0.0
        self._heading, self._go = self._breach_move(me)
        return True

    def _breach_move(self, me):
        """Курс на стену; подъезжаем до BREACH_RANGE_M, дальше стоим и стреляем."""
        px, py = self._breach_point
        heading = bearing_deg(me.x, me.y, px, py)
        far = math.hypot(px - me.x, py - me.y) > BREACH_RANGE_M * PX_PER_M
        return heading, (1.0 if far else 0.0)

    def _stop_breach(self):
        self._breach_wall = None
        self.intent = Intent.ADVANCE
        self._hold = 0.0

    def _choose(self, me, enemy, dist, engage):
        frac = damage_by_aspect(me, enemy)
        seen_from = abs(shortest_angle_diff(
            bearing_deg(enemy.x, enemy.y, me.x, me.y), enemy.hull_angle))
        already_flanked = seen_from > 60.0

        need = 1.0 - frac["front"]                                # насколько лоб мне не по зубам
        flank_pays = max(frac["side"], frac["rear"]) > 0.7
        if (not already_flanked and flank_pays
                and need * (0.5 + self.arch.flank_bias) > 0.6):
            return Intent.FLANK
        return Intent.ENGAGE if dist <= engage * 1.3 else Intent.ADVANCE

    # ---------- огонь ----------
    def _gunnery(self, dt, me, enemy, ctx, aim_point):
        err = shortest_angle_diff(bearing_deg(me.x, me.y, *aim_point), me.turret_angle)
        target = self._breach_wall if self.intent is Intent.BREACH else enemy
        if abs(err) > 6.0:
            self._react_left = None
            return False

        info = compute_aim(me, ctx.targets)                       # то же, что видит игрок
        res = info.result
        if not (info.target is target and res is not None and res.damage_frac >= MIN_USEFUL_DAMAGE):
            self._react_left = None
            return False

        if self._react_left is None:                              # линия огня только что появилась
            self._react_left = self.rng.uniform(*self.skill.reaction)
        self._react_left -= dt
        return (self._react_left <= 0.0 and abs(err) <= FIRE_TOLERANCE_DEG
                and me.reload_left <= 0.0)