"""ai/brain.py — мозг бота: выбор намерения по баллам и диспетчеризация планировщиков
(Navigator, CoverPlanner, BreachPlanner), фланг, решение о выстреле."""
import math
from enum import Enum, auto

from engine import VehicleCommand, shortest_angle_diff, clamp, PX_PER_M, heading_vector, bearing_deg
from combat import compute_aim
from .steering import steer_to, StuckGuard
from .gunnery import (lead_point, evaluate_matchup,
                      outflank_feasibility, preferred_distance_m, best_hull_heading,
                      shot_fraction_now, shot_geometry, best_ammo,
                      MIN_USEFUL_DAMAGE, NO_DAMAGE)
from .navigator import Navigator
from .breach import BreachPlanner
from .cover_planner import CoverPlanner, COVER_RETRY_S

class Intent(Enum):
    ADVANCE = auto()
    ENGAGE = auto()
    FLANK = auto()
    BREACH = auto()      # ломать стену, которая мешает
    COVER = auto()       # спрятаться и ждать

# --- позиция относительно цели (обход к корме / удержание лба) ---
ORBIT_STEP_DEG = 40.0        # на сколько градусов вперёд по орбите ставим путевую точку
FLANK_GIVEUP_S = 14.0        # дольше этого к позиции не пробиваемся
FLANK_COOLDOWN_S = 8.0       # пауза в обходах после неудачи
HOLD_MIN_S = 1.5             # минимальное время удержания намерения (гистерезис)
HOLD_SPREAD_S = 1.0          # плюс случайная добавка до этого значения
FIRE_GATE_DEG = 6.0          # башня дальше этого от цели: линию огня даже не проверяем

# --- бить нечем: пора обходить ---
FUTILE_REACT_S = 0.6         # сколько секунд урон должен быть «гарантированно» ниже NO_DAMAGE

# --- баллы намерений (_choose) ---
INTENT_STICKY = 0.4          # бонус к баллу текущего намерения (против дрожания решений)
IN_RANGE_K = 1.3             # «в зоне боя»: дистанция не больше engage * этого
FLANKED_ANGLE_DEG = 60.0     # геометрически уже сбоку или сзади (нужно для укрытий)
DUEL_CLAMP = 2.0             # потолок оценки дуэли в лоб (log2)
GAIN_CLAMP = 3.0             # потолок выигрыша от фланга (log2)
ENGAGE_BASE, ENGAGE_DUEL_K = 1.0, 0.5
ENGAGE_IN_RANGE, ENGAGE_OUT_RANGE = 0.8, -0.6
ADVANCE_BASE = 0.8
ADVANCE_IN_RANGE, ADVANCE_OUT_RANGE = -0.4, 0.6
FLANK_BLOCKED = -9.0         # фланг запрещён (уже на позиции или пауза после неудачи)
FLANK_GAIN_K, FLANK_DUEL_K, FLANK_BASE = 1.2, 0.5, -0.6
FUTILE_ENGAGE_PENALTY = 3.0
FUTILE_ADVANCE_PENALTY = 1.5
FUTILE_FLANK_BONUS = 2.5
COVER_REACH_K = 1.1          # укрытие рассматриваем, если враг достаёт: дистанция <= дальность * этого
COVER_FEAR_DUEL_K = 0.8      # страх от проигрышного матчапа
COVER_FEAR_LOW_HP = 3.0      # базовый страх при HP ниже порога архетипа
COVER_FEAR_LOW_HP_K = 2.5    # плюс растёт по мере падения HP
COVER_FEAR_TRAPPED = 2.5     # бить нечем, а обходить уже некуда
COVER_BASE = -1.0

# --- движение на дистанции боя ---
ENGAGE_FAR_K = 1.15          # дальше engage * этого: подъезжаем
ENGAGE_NEAR_K = 0.6          # ближе engage * этого: сдаём назад

BREACH_AMMO_COS = 0.85       # при выборе снаряда против стены берём «средний» угол
FIRE_TOLERANCE_DEG = 2.0

class BotBrain:
    def __init__(self, arch, skill, rng):
        self.arch, self.skill, self.rng = arch, skill, rng
        self.intent = Intent.ADVANCE
        self.stuck = StuckGuard()
        self.nav = Navigator(rng)
        self.cover = CoverPlanner(self.nav)
        self.breach = BreachPlanner()
        self._clock = 0.0                                         # время жизни мозга, с (нужно обходу)
        self._hold = 0.0                                          # сколько ещё держим намерение
        self._think_in = rng.uniform(0.0, 1.0 / skill.think_hz)   # сдвиг фаз между ботами
        self._heading, self._go = 0.0, 0.0                        # результат последнего «размышления»
        self._flank_t = 0.0                                       # сколько секунд подряд идёт обход
        self._flank_block_until = 0.0                             # до этого момента обход запрещён
        self._flank_side = rng.choice((-1, 1))
        self._react_left = None                                   # None: чистой линии огня нет
        self._futile_t = 0.0                                      # сколько секунд подряд бить нечем
        self._was_reversing = False
        self._m_key = None
        self._m = None

    # ==========================================
    # КАДР
    # ==========================================
    def think(self, dt, me, enemy, ctx):
        """ctx — объект с полями targets, terrain, walls, fleet, budget, nav"""
        if not enemy.alive:
            return VehicleCommand()

        self._clock += dt
        self._hold -= dt
        self._think_in -= dt
        self.nav.tick(dt)
        self.cover.tick(dt)
        self.breach.tick(dt)
        if self._think_in <= 0.0:                                 # редко: решения и проверки местности
            self._think_in += 1.0 / self.skill.think_hz
            self._decide(me, enemy, ctx)

        if self.intent is Intent.BREACH:
            aim = self.breach.point
        else:
            aim = lead_point(me, enemy, self.skill.lead_k)        # каждый кадр: дёшево

        # Стоим на месте, а цель вне сектора наводки орудия: доворачиваем КОРПУС (для круговой башни offset = 0)
        heading = self._heading
        if self._go == 0.0:
            off = me.hull_offset_to(*aim)
            if off != 0.0:
                heading = me.hull_angle + off

        throttle, steer = steer_to(me, heading, self._go)
        # «давит» = пытается ехать ИЛИ поворачиваться (иначе заклинивший поворот на месте не виден)
        reversing = self.stuck.update(dt, me, (throttle != 0.0 or steer != 0.0) and not me.stunned, self.rng)
        if reversing:
            if not self._was_reversing:
                self.nav.remember_stuck(me)
            throttle, steer = -1.0, self.stuck.turn
        self._was_reversing = reversing

        fire = self._gunnery(dt, me, enemy, ctx, aim)
        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim, fire=fire)

    # ==========================================
    # РЕШЕНИЕ
    # ==========================================
    def _decide(self, me, enemy, ctx):
        dist = math.hypot(enemy.x - me.x, enemy.y - me.y)
        engage = preferred_distance_m(me, enemy, self.arch.engage_dist_m, self.arch.edge_k) * PX_PER_M
        tick = 1.0 / self.skill.think_hz
        futile = self._update_futile(me, enemy, dist, tick)

        if self.intent is Intent.BREACH:                          # идёт прорыв
            if self.breach.finished():
                self._stop_breach()                               # стена рухнула или время вышло
            else:
                self._heading, self._go = self.breach.move(me)
                return

        if self.intent is Intent.COVER and self._run_cover(me, enemy, ctx, dist, tick):
            return                                                # продолжаем прятаться; иначе вышли и выбираем заново

        seen = self._seen_from(me, enemy)
        arrived = self.intent is Intent.FLANK and self._in_position(seen)
        if self.intent is Intent.FLANK:
            self._flank_t += tick
            if self._flank_t > FLANK_GIVEUP_S:                    # не получается добраться
                self._flank_block_until = self._clock + FLANK_COOLDOWN_S
                self._hold = 0.0

        # бить нечем: не ждём конца гистерезиса, сразу пересматриваем
        if self._hold <= 0.0 or arrived or (futile and self.intent in (Intent.ENGAGE, Intent.ADVANCE)):
            intent = self._choose(me, enemy, dist, engage, futile)
            if intent is Intent.COVER and not self.cover.begin(me, enemy, ctx):
                self.cover.block(COVER_RETRY_S)                   # укрытия нет: выбираем без него
                intent = self._choose(me, enemy, dist, engage, futile)
            if intent is not self.intent:
                self.nav.invalidate()
                if intent is Intent.FLANK:
                    self._flank_side = self._pick_flank_side(me, enemy, ctx)
                    self._flank_t = 0.0
            self.intent = intent
            self._hold = HOLD_MIN_S + self.rng.random() * HOLD_SPREAD_S
            if intent is Intent.COVER and self._run_cover(me, enemy, ctx, dist, 0.0):
                return

        if self.intent is Intent.FLANK:
            goal = self._aspect_goal(me, enemy, engage)
            go = 1.0
        else:
            goal = (enemy.x, enemy.y)
            if self.intent is Intent.ENGAGE:
                go = (1.0 if dist > engage * ENGAGE_FAR_K
                      else (-1.0 if dist < engage * ENGAGE_NEAR_K else 0.0))
            else:
                go = 1.0
        want = bearing_deg(me.x, me.y, *goal)

        if go > 0.0:
            res = self._drive(me, ctx, goal, want)
            if res is None:                                       # начался прорыв
                return
            want, go = res
        elif go == 0.0 and self.intent is Intent.ENGAGE:          # стоим на позиции
            if self._try_breach(me, ctx, want, dist):             # линию огня закрыла стена
                return
            if me.spec.TURRET_ARC_DEG >= 360.0:                   # круговая башня: можно подставлять выгодный угол,
                want = best_hull_heading(me, enemy, want)         # ограниченный сектор требует смотреть прямо на цель
        if go < 0.0 and Navigator.rear_blocked(me, ctx):
            go = 0.0                                              # сзади занято: стоим, а не упираемся
        self._heading, self._go = want, go

    # ---------- связки с планировщиками ----------
    def _drive(self, me, ctx, goal, want):
        """Езда к цели по пути A*. None: началось прорыв стены."""
        return self.nav.drive_to(me, ctx, goal, want,
                                 on_wall=lambda wall: self._breach_via_path(me, ctx, wall))

    def _breach_via_path(self, me, ctx, wall):
        if self.breach.begin_from_path(me, ctx, wall):
            self._enter_breach(me)
            return True
        return False

    def _try_breach(self, me, ctx, bearing, look_px):
        if self.breach.begin_ahead(me, ctx, bearing, look_px):
            self._enter_breach(me)
            return True
        return False

    def _enter_breach(self, me):
        self.intent = Intent.BREACH
        self._hold = 0.0
        self._heading, self._go = self.breach.move(me)

    def _stop_breach(self):
        self.breach.stop()
        self.intent = Intent.ADVANCE
        self._hold = 0.0
        self.nav.invalidate()                                     # стены уже нет: путь строим заново

    def _run_cover(self, me, enemy, ctx, dist, tick):
        """Шаг укрытия. True: прячемся дальше. False: вышли, намерение сброшено на ADVANCE."""
        self.cover.heading, self.cover.go = self._heading, self._go   # на случай, если step не выставит команду
        if self.cover.step(me, enemy, ctx, dist, tick):
            self._heading, self._go = self.cover.heading, self.cover.go
            return True
        self.intent = Intent.ADVANCE
        self._hold = 0.0
        return False

    # ---------- фланг и позиция ----------
    @staticmethod
    def _nearer_flank(me, enemy):
        """Какой борт врага ближе ко мне: +1 правый, -1 левый (как в flank_point)."""
        fx, fy = heading_vector(enemy.hull_angle)
        rx, ry = -fy, fx
        return 1 if (me.x - enemy.x) * rx + (me.y - enemy.y) * ry >= 0.0 else -1

    def _pick_flank_side(self, me, enemy, ctx):
        """Ближний борт, но если по нему уже кто-то обходит, берём противоположный."""
        near = self._nearer_flank(me, enemy)
        load = 0
        for b in ctx.fleet.bots:
            brain = b.brain
            if brain is not self and brain.intent is Intent.FLANK:
                load += brain._flank_side                         # +1 справа, -1 слева
        return -near if near * load >= 1 else near

    @staticmethod
    def _seen_from(me, enemy):
        """Под каким углом к лбу цели я нахожусь: 0 лоб, 90 борт, 180 корма."""
        return abs(shortest_angle_diff(
            bearing_deg(enemy.x, enemy.y, me.x, me.y), enemy.hull_angle))

    def _in_position(self, seen_from):
        """Я уже там, где хочет быть мой архетип?"""
        return abs(seen_from - self.arch.aspect_deg) <= self.arch.aspect_tol_deg

    def _aspect_goal(self, me, enemy, dist_px):
        """Путевая точка на орбите вокруг цели: на пути от моего текущего угла к желаемому.
        Едем по спирали, а не напрямую, чтобы не проезжать через лоб цели."""
        fx, fy = heading_vector(enemy.hull_angle)
        rx, ry = -fy, fx                                          # вправо от корпуса цели
        dx, dy = me.x - enemy.x, me.y - enemy.y
        theta = math.degrees(math.atan2(dx * rx + dy * ry, dx * fx + dy * fy))   # со знаком: + справа
        goal = self._flank_side * self.arch.aspect_deg
        diff = shortest_angle_diff(goal, theta)
        if abs(diff) > 150.0:                                     # почти противоположная сторона: берём свою
            diff = math.copysign(abs(diff), self._flank_side)
        step = clamp(diff, -ORBIT_STEP_DEG, ORBIT_STEP_DEG)
        t = math.radians(theta + step)
        c, s = math.cos(t), math.sin(t)
        return (enemy.x + (fx * c + rx * s) * dist_px,
                enemy.y + (fy * c + ry * s) * dist_px)

    def _update_futile(self, me, enemy, dist, tick):
        """True, если из текущей позиции урон «гарантированно» меньше NO_DAMAGE уже FUTILE_REACT_S секунд."""
        if dist > me.spec.SHELL_RANGE_PX:
            self._futile_t = 0.0
            return False
        if shot_fraction_now(me, enemy) < NO_DAMAGE:
            self._futile_t += tick
        else:
            self._futile_t = 0.0
        return self._futile_t >= FUTILE_REACT_S

    # ---------- намерение по баллам ----------
    def _matchup(self, me, enemy):
        """Матчап зависит от HP, поэтому пересчитываем при смене «ведра» 10% у любого из танков."""
        key = (int(10 * me.hp / me.max_hp), int(10 * enemy.hp / enemy.max_hp), id(me.spec), id(enemy.spec))
        if key != self._m_key:
            self._m_key = key
            self._m = evaluate_matchup(me, enemy)
        return self._m

    def _choose(self, me, enemy, dist, engage, futile):
        m = self._matchup(me, enemy)
        seen_from = self._seen_from(me, enemy)
        flanked = seen_from > FLANKED_ANGLE_DEG                   # геометрически уже сбоку или сзади (для укрытий)
        in_position = self._in_position(seen_from)
        in_range = dist <= engage * IN_RANGE_K

        duel = clamp(math.log2(m.front_ratio), -DUEL_CLAMP, DUEL_CLAMP)    # >0: в лоб драться выгодно
        gain = clamp(math.log2(m.flank_ratio / m.front_ratio), 0.0, GAIN_CLAMP)   # насколько фланг лучше лба
        mobility = outflank_feasibility(me, enemy, dist)          # 0..1: успею ли обойти

        flank_blocked = in_position or self._clock < self._flank_block_until
        scores = {
            Intent.ENGAGE: (ENGAGE_BASE + ENGAGE_DUEL_K * duel
                            + (ENGAGE_IN_RANGE if in_range else ENGAGE_OUT_RANGE)),
            Intent.ADVANCE: ADVANCE_BASE + (ADVANCE_IN_RANGE if in_range else ADVANCE_OUT_RANGE),
            Intent.FLANK: (FLANK_BLOCKED if flank_blocked else
                           self.arch.flank_bias + self.arch.aspect_drive
                           + FLANK_GAIN_K * gain * mobility - FLANK_DUEL_K * duel + FLANK_BASE),
        }
        if futile:                                                # отсюда бить нечем: нужен обход
            scores[Intent.ENGAGE] -= FUTILE_ENGAGE_PENALTY
            scores[Intent.ADVANCE] -= FUTILE_ADVANCE_PENALTY
            if not in_position:
                scores[Intent.FLANK] += FUTILE_FLANK_BONUS

        # укрытие: только когда игрок достаёт и пауза после прошлого укрытия прошла
        if self.cover.available and dist <= enemy.spec.SHELL_RANGE_PX * COVER_REACH_K:
            fear = COVER_FEAR_DUEL_K * max(0.0, -duel)            # проигрышный матчап
            low = self.arch.retreat_hp
            hp_frac = me.hp / me.max_hp if me.max_hp > 0 else 1.0
            if low > 0.0 and hp_frac < low:                       # мало здоровья
                fear += COVER_FEAR_LOW_HP + COVER_FEAR_LOW_HP_K * (1.0 - hp_frac / low)
            if futile and flanked:                                # бить нечем, а обходить уже некуда
                fear += COVER_FEAR_TRAPPED
            scores[Intent.COVER] = self.arch.cover_bias + fear + COVER_BASE

        if self.intent in scores:
            scores[self.intent] += INTENT_STICKY
        return max(scores, key=scores.get)

    # ==========================================
    # ОГОНЬ
    # ==========================================

    def _pick_ammo(self, me, enemy):
        """Выбор снаряда: по игроку (по реальной грани, углу и гусенице) либо по стене при прорыве.
        Смена идёт через select_ammo: прогресс перезарядки сохраняется пропорционально."""
        wall = self.breach.wall if self.intent is Intent.BREACH else None
        if wall is not None:
            kind = best_ammo(me, wall, None, BREACH_AMMO_COS, None)
        else:
            normal, cos_i, point = shot_geometry(me, enemy)
            kind = best_ammo(me, enemy, normal, cos_i, point)
        if kind is not me.ammo:
            me.select_ammo(kind)

    def _gunnery(self, dt, me, enemy, ctx, aim_point):
        err = shortest_angle_diff(bearing_deg(me.x, me.y, *aim_point), me.turret_angle)
        breaching = self.intent is Intent.BREACH
        target = self.breach.wall if breaching else enemy
        # по врагу стреляем уже от 5% урона, по стене только от 15% (по этому порогу считалось время прорыва)
        min_frac = MIN_USEFUL_DAMAGE if breaching else NO_DAMAGE
        if abs(err) > FIRE_GATE_DEG:
            self._react_left = None
            return False

        info = compute_aim(me, ctx.targets)                       # то же, что видит игрок
        res = info.result
        frac = 0.0 if res is None else max(res.damage_frac, info.min_frac)   # фугас бьёт осколками и сквозь броню
        if not (info.target is target and res is not None and frac >= min_frac):
            self._react_left = None
            return False

        if self._react_left is None:                              # линия огня только что появилась
            self._react_left = self.rng.uniform(*self.skill.reaction)
        self._react_left -= dt
        return (self._react_left <= 0.0 and abs(err) <= FIRE_TOLERANCE_DEG
                and me.reload_left <= 0.0)