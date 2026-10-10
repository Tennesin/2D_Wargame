"""ai/brain.py — мозг бота: намерение (по баллам), путь A*, прорыв стен, укрытия, решение о выстреле."""
import math
from enum import Enum, auto

from engine import VehicleCommand, shortest_angle_diff, clamp, PX_PER_M, heading_vector
from combat import compute_aim
from .steering import bearing_deg, steer_to, pick_heading, StuckGuard
from .gunnery import (lead_point, flank_point, seconds_to_break, evaluate_matchup,
                      outflank_feasibility, preferred_distance_m, best_hull_heading,
                      shot_fraction_now, BREACH_MAX_S, MIN_USEFUL_DAMAGE, NO_DAMAGE)
from .pathfinding import find_path
from .cover import find_cover, shield_between, attention

# Флаги для поэтапной проверки
AI_MOVE_ENABLED = True
AI_FIRE_ENABLED = True
USE_ASTAR = True              # False: старые «щупальца» (удобно сравнивать поведение)

class Intent(Enum):
    ADVANCE = auto()
    ENGAGE = auto()
    FLANK = auto()
    BREACH = auto()      # ломать стену, которая мешает
    COVER = auto()       # спрятаться и ждать

# --- прорыв стен ---
BREACH_RANGE_M = 14.0        # с какого расстояния стреляем по стене
BREACH_TRIGGER_M = 25.0      # стена на пути ближе этого: пора решать, ломать ли её
BREACH_LOOK_M = 30.0         # (запасной режим без A*) как далеко вперёд ищем мешающую стену
BREACH_DETOUR_DEG = 50.0     # (запасной режим) объезд круче этого считается плохим

# --- перепланирование пути ---
REPLAN_S = 1.5               # период перепланирования (с разбросом ±20%)
REPLAN_GOAL_M = 10.0         # цель сместилась больше чем на это
REPLAN_OFFPATH_M = 6.0       # бот ушёл с пути дальше этого
FORBID_WALL_S = 15.0         # сколько секунд «непробиваемой» считается стена, с которой не вышло
STUCK_SPOT_S = 12.0          # сколько секунд помним место, где застряли

# --- бить нечем: пора обходить ---
FUTILE_REACT_S = 0.6         # сколько секунд урон должен быть «гарантированно» ниже NO_DAMAGE

# --- укрытия ---
COVER_ARRIVE_M = 4.5         # приехали к точке укрытия
COVER_HOLD_M = 7.0           # уже спрятан и ближе этого к точке: можно ждать
COVER_CALM_S = 2.0           # сколько игрок должен «смотреть мимо», чтобы мы вышли (на другого бота вдвое быстрее)
COVER_PANIC_M = 12.0         # игрок смотрит на нас и ближе этого: укрытие не спасёт, выходим драться
COVER_MAX_S = 25.0           # дольше не прячемся
COVER_COOLDOWN_S = 7.0       # пауза до следующего укрытия после «игрок отвернулся»
COVER_FIGHT_S = 10.0         # пауза после «прижали» или неудачи
COVER_RETRY_S = 3.0          # пауза, если подходящего укрытия не нашлось
COVER_MAX_TRIES = 3          # сколько раз подряд меняем укрытие
COVER_BAD_S = 12.0           # сколько секунд помним негодное укрытие
COVER_HP_DROP = 0.05         # потеряли столько HP (доля максимума) в укрытии: оно не работает

INTENT_STICKY = 0.4          # бонус к баллу текущего намерения (против дрожания решений)
FIRE_TOLERANCE_DEG = 2.0

class BotBrain:
    def __init__(self, arch, skill, rng):
        self.arch, self.skill, self.rng = arch, skill, rng
        self.intent = Intent.ADVANCE
        self.stuck = StuckGuard()
        self._clock = 0.0                                         # время жизни мозга, с
        self._hold = 0.0                                          # сколько ещё держим намерение
        self._think_in = rng.uniform(0.0, 1.0 / skill.think_hz)   # сдвиг фаз между ботами
        self._heading, self._go = 0.0, 0.0                        # результат последнего «размышления»
        self._flank_side = rng.choice((-1, 1))
        self._avoid_side = rng.choice((-1, 1))
        self._react_left = None                                   # None: чистой линии огня нет
        self._futile_t = 0.0                                      # сколько секунд подряд бить нечем
        # прорыв
        self._breach_wall = None
        self._breach_point = (0.0, 0.0)
        self._breach_left = 0.0
        # укрытие
        self._cover_pt = None
        self._cover_state = "move"                                # "move" едем, "hold" ждём
        self._cover_t = 0.0
        self._calm_t = 0.0
        self._cover_hp0 = 0.0
        self._cover_tries = 0
        self._cover_block_until = 0.0                             # до этого момента в укрытие не идём
        self._bad_cover = []                                      # [[x, y, ttl], ...]
        # путь
        self._path = None
        self._replan_in = 0.0
        self._forbidden = {}                                      # id стены -> секунд до снятия запрета
        self._bad_spots = []                                      # [[x, y, ttl], ...] места застревания
        self._was_reversing = False
        # матчап
        self._m_key = None
        self._m = None

    # ==========================================
    # КАДР
    # ==========================================
    def think(self, dt, me, enemy, ctx):
        """ctx — объект с полями targets (TargetSet), terrain, walls, fleet."""
        if not enemy.alive:
            return VehicleCommand()

        self._clock += dt
        self._hold -= dt
        self._think_in -= dt
        self._replan_in -= dt
        self._tick_memory(dt)
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
        # «давит» = пытается ехать ИЛИ поворачиваться (иначе заклинивший поворот на месте не виден)
        reversing = self.stuck.update(dt, me, throttle != 0.0 or steer != 0.0, self.rng)
        if reversing:
            if not self._was_reversing:
                self._remember_stuck(me)
            throttle, steer = -1.0, self.stuck.turn
        self._was_reversing = reversing
        if not AI_MOVE_ENABLED:
            throttle, steer = 0.0, 0.0

        fire = self._gunnery(dt, me, enemy, ctx, aim) and AI_FIRE_ENABLED
        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim, fire=fire)

    def _tick_memory(self, dt):
        """Запреты на стены, «плохие места» и негодные укрытия со временем забываются."""
        if self._forbidden:
            self._forbidden = {k: t - dt for k, t in self._forbidden.items() if t - dt > 0.0}
        for spots in (self._bad_spots, self._bad_cover):
            if spots:
                for s in spots:
                    s[2] -= dt
                spots[:] = [s for s in spots if s[2] > 0.0]

    def _remember_stuck(self, me):
        """Бот застрял: помечаем место впереди штрафом и перестраиваем путь."""
        fx, fy = heading_vector(me.hull_angle)
        self._bad_spots.append([me.x + fx * 400.0, me.y + fy * 400.0, STUCK_SPOT_S])
        self._invalidate()

    # ==========================================
    # РЕШЕНИЕ
    # ==========================================
    def _decide(self, me, enemy, ctx):
        dist = math.hypot(enemy.x - me.x, enemy.y - me.y)
        engage = preferred_distance_m(me, enemy, self.arch.engage_dist_m, self.arch.edge_k) * PX_PER_M
        tick = 1.0 / self.skill.think_hz
        futile = self._update_futile(me, enemy, dist, tick)

        if self.intent is Intent.BREACH:                          # идёт прорыв
            wall = self._breach_wall
            if wall is None or not wall.alive or self._breach_left <= 0.0:
                self._stop_breach()                               # стена рухнула или время вышло
            else:
                self._heading, self._go = self._breach_move(me)
                return

        if self.intent is Intent.COVER:                           # прячемся
            if self._cover_step(me, enemy, ctx, dist, tick):
                return                                            # продолжаем прятаться; иначе вышли и выбираем заново

        # бить нечем: не ждём конца гистерезиса, сразу пересматриваем
        if self._hold <= 0.0 or (futile and self.intent in (Intent.ENGAGE, Intent.ADVANCE)):
            intent = self._choose(me, enemy, dist, engage, futile)
            if intent is Intent.COVER and not self._begin_cover(me, enemy, ctx):
                self._cover_block_until = self._clock + COVER_RETRY_S    # укрытия нет: выбираем без него
                intent = self._choose(me, enemy, dist, engage, futile)
            if intent is not self.intent:
                self._invalidate()
                if intent is Intent.FLANK:
                    self._flank_side = self._nearer_flank(me, enemy)
            self.intent = intent
            self._hold = 1.5 + self.rng.random()                  # гистерезис
            if intent is Intent.COVER and self._cover_step(me, enemy, ctx, dist, 0.0):
                return

        if self.intent is Intent.FLANK:
            goal = flank_point(enemy, engage, self._flank_side)
            go = 1.0
        else:
            goal = (enemy.x, enemy.y)
            if self.intent is Intent.ENGAGE:
                go = 1.0 if dist > engage * 1.15 else (-1.0 if dist < engage * 0.6 else 0.0)
            else:
                go = 1.0
        want = bearing_deg(me.x, me.y, *goal)

        if go > 0.0:
            res = self._drive_to(me, ctx, goal, want, dist)
            if res is None:                                       # начался прорыв
                return
            want, go = res
        elif go == 0.0 and self.intent is Intent.ENGAGE:          # стоим на позиции
            if self._try_breach(me, ctx, want, dist):             # линию огня закрыла стена
                return
            want = best_hull_heading(me, enemy, want)             # выгодный угол корпуса
        self._heading, self._go = want, go

    @staticmethod
    def _nearer_flank(me, enemy):
        """Какой борт врага ближе ко мне: +1 правый, -1 левый (как в flank_point)."""
        fx, fy = heading_vector(enemy.hull_angle)
        rx, ry = -fy, fx
        return 1 if (me.x - enemy.x) * rx + (me.y - enemy.y) * ry >= 0.0 else -1

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
        seen_from = abs(shortest_angle_diff(
            bearing_deg(enemy.x, enemy.y, me.x, me.y), enemy.hull_angle))
        flanked = seen_from > 60.0                                # я уже у него сбоку или сзади
        in_range = dist <= engage * 1.3

        duel = clamp(math.log2(m.front_ratio), -2.0, 2.0)         # >0: в лоб драться выгодно
        gain = clamp(math.log2(m.flank_ratio / m.front_ratio), 0.0, 3.0)   # насколько фланг лучше лба
        mobility = outflank_feasibility(me, enemy, dist)          # 0..1: успею ли обойти

        scores = {
            Intent.ENGAGE: 1.0 + 0.5 * duel + (0.8 if in_range else -0.6),
            Intent.ADVANCE: 0.8 + (-0.4 if in_range else 0.6),
            Intent.FLANK: (-9.0 if flanked else
                           self.arch.flank_bias + 1.2 * gain * mobility - 0.5 * duel - 0.6),
        }
        if futile:                                                # отсюда бить нечем: нужен обход
            scores[Intent.ENGAGE] -= 3.0
            scores[Intent.ADVANCE] -= 1.5
            if not flanked:
                scores[Intent.FLANK] += 2.5

        # укрытие: только когда игрок достаёт и пауза после прошлого укрытия прошла
        if self._clock >= self._cover_block_until and dist <= enemy.spec.SHELL_RANGE_PX * 1.1:
            fear = 0.8 * max(0.0, -duel)                          # проигрышный матчап
            low = self.arch.retreat_hp
            hp_frac = me.hp / me.max_hp if me.max_hp > 0 else 1.0
            if low > 0.0 and hp_frac < low:                       # мало здоровья
                fear += 3.0 + 2.5 * (1.0 - hp_frac / low)
            if futile and flanked:                                # бить нечем, а обходить уже некуда
                fear += 2.5
            scores[Intent.COVER] = self.arch.cover_bias + fear - 1.0

        if self.intent in scores:
            scores[self.intent] += INTENT_STICKY
        return max(scores, key=scores.get)

    # ---------- укрытие ----------
    def _begin_cover(self, me, enemy, ctx):
        """Начать прятаться: ищем точку. False, если подходящей нет."""
        self._cover_t = 0.0
        self._cover_tries = 0
        self._calm_t = 0.0
        return self._pick_cover(me, enemy, ctx)

    def _pick_cover(self, me, enemy, ctx):
        spot = find_cover(me, enemy, ctx, self._bad_cover)
        if spot is None:
            return False
        self._cover_pt = spot
        self._cover_state = "move"
        self._invalidate()
        return True

    def _cover_step(self, me, enemy, ctx, dist, tick):
        """Один шаг укрытия. True: продолжаем прятаться (курс и газ выставлены). False: вышли из укрытия."""
        self._cover_t += tick
        if self._cover_t > COVER_MAX_S:
            return self._leave_cover(COVER_COOLDOWN_S)

        cx, cy = self._cover_pt
        d_pt = math.hypot(cx - me.x, cy - me.y)
        hidden = shield_between(ctx, enemy, me.x, me.y) is not None   # закрыт ли я прямо сейчас

        if self._cover_state == "move":
            if hidden and d_pt <= COVER_HOLD_M * PX_PER_M:
                self._cover_state = "hold"
                self._calm_t = 0.0
                self._cover_hp0 = me.hp
            elif d_pt <= COVER_ARRIVE_M * PX_PER_M:
                return self._cover_retry(me, enemy, ctx)              # приехали, а тут не прикрыто
            else:
                res = self._drive_to(me, ctx, (cx, cy), bearing_deg(me.x, me.y, cx, cy), d_pt,
                                     no_breach=True)
                self._heading, self._go = res
                return True

        # состояние "hold"
        if not hidden or me.hp < self._cover_hp0 - COVER_HP_DROP * me.max_hp:
            return self._cover_retry(me, enemy, ctx)                  # игрок сместился, стена рухнула или бьют
        att = attention(enemy, me, [b.tank for b in ctx.fleet.bots])
        if att == "me":
            self._calm_t = 0.0
            if dist < COVER_PANIC_M * PX_PER_M:
                return self._leave_cover(COVER_FIGHT_S)               # прижали: драться
        else:
            self._calm_t += tick * (2.0 if att == "other" else 1.0)  # игрок занят другим
            if self._calm_t >= COVER_CALM_S:
                return self._leave_cover(COVER_COOLDOWN_S)
        self._heading = best_hull_heading(me, enemy, bearing_deg(me.x, me.y, enemy.x, enemy.y))
        self._go = 0.0
        return True

    def _cover_retry(self, me, enemy, ctx):
        """Это укрытие не работает: запоминаем его и текущую точку как плохие и ищем другое."""
        cx, cy = self._cover_pt
        self._bad_cover.append([cx, cy, COVER_BAD_S])
        self._bad_cover.append([me.x, me.y, COVER_BAD_S])
        self._cover_tries += 1
        if self._cover_tries >= COVER_MAX_TRIES or not self._pick_cover(me, enemy, ctx):
            return self._leave_cover(COVER_FIGHT_S)
        return True

    def _leave_cover(self, cooldown):
        """Выход из укрытия. Всегда возвращает False (удобно для _cover_step)."""
        self._cover_pt = None
        self.intent = Intent.ADVANCE
        self._hold = 0.0
        self._cover_block_until = self._clock + cooldown
        self._invalidate()
        return False

    # ---------- движение ----------
    def _invalidate(self):
        self._path = None
        self._replan_in = 0.0

    def _plan(self, me, ctx, goal, no_breach=False):
        """Текущий путь; перестраивается по таймеру, при смене цели, при уходе с пути и по прибытии."""
        p = self._path
        need = self._replan_in <= 0.0
        if p is not None and not need:
            need = (math.hypot(goal[0] - p.goal[0], goal[1] - p.goal[1]) > REPLAN_GOAL_M * PX_PER_M
                    or p.deviation_px(me.x, me.y) > REPLAN_OFFPATH_M * PX_PER_M
                    or p.done(me.x, me.y))
        if need:
            self._path = find_path(me, goal, ctx.terrain, ctx.walls,
                                   self._forbidden, self._bad_spots, no_breach)
            self._replan_in = REPLAN_S * self.rng.uniform(0.8, 1.2)
        return self._path

    def _drive_to(self, me, ctx, goal, want, dist, no_breach=False):
        """Курс и газ при езде к точке goal. None: бот перешёл в BREACH (при no_breach не бывает)."""
        if USE_ASTAR:
            for _ in range(2):          # второй проход нужен после запрета непробиваемой стены
                path = self._plan(me, ctx, goal, no_breach)
                if path is None:
                    break
                wall = path.breach_wall
                to_wall = (math.hypot(wall.x - me.x, wall.y - me.y) - wall.radius_px
                           if wall is not None else None)
                if wall is None or to_wall > BREACH_TRIGGER_M * PX_PER_M:
                    return bearing_deg(me.x, me.y, *path.next_point(me.x, me.y)), 1.0
                if self._breach_path_wall(me, wall):
                    return None
                self._forbidden[id(wall)] = FORBID_WALL_S         # с этого угла не выходит: считаем стену глухой
                self._invalidate()
        # запасной режим: пути нет (или A* выключен), работают «щупальца»
        heading = pick_heading(me, ctx.terrain, ctx.walls, want, 1000.0, self._avoid_side)
        detour = 180.0 if heading is None else abs(shortest_angle_diff(heading, want))
        look = min(dist, BREACH_LOOK_M * PX_PER_M)
        if not no_breach and detour >= BREACH_DETOUR_DEG and self._try_breach(me, ctx, want, look):
            return None
        if heading is None:                                       # всё занято: разворот на месте
            self._avoid_side = -self._avoid_side
            return want + 90.0 * self._avoid_side, 0.0
        return heading, 1.0

    # ---------- прорыв стены ----------
    def _try_breach(self, me, ctx, bearing, look_px):
        """Есть ли по курсу bearing стена, которую выгодно ломать (проверка лучом)."""
        fx, fy = heading_vector(bearing)
        tx, ty = me.x + fx * look_px, me.y + fy * look_px
        hit = ctx.walls.raycast(me.x, me.y, tx, ty)
        if hit is None:
            return False
        wall, t, normal = hit
        point = (me.x + (tx - me.x) * t, me.y + (ty - me.y) * t)
        return self._start_breach(me, wall, point, normal, bearing)

    def _breach_path_wall(self, me, wall):
        """Стена из пути A*: целимся в ближайшую к боту точку её поверхности по линии на центр стены."""
        res = wall.segment_hit(me.x, me.y, wall.x, wall.y)
        if res is None:
            return False
        t, normal = res
        point = (me.x + (wall.x - me.x) * t, me.y + (wall.y - me.y) * t)
        return self._start_breach(me, wall, point, normal, bearing_deg(me.x, me.y, wall.x, wall.y))

    def _start_breach(self, me, wall, point, normal, bearing):
        """Проверка по реальному углу попадания; при успехе переходим в BREACH."""
        fx, fy = heading_vector(bearing)
        cos_i = 1.0 if normal is None else abs(fx * normal[0] + fy * normal[1])
        secs = seconds_to_break(me, wall, cos_i, normal, MIN_USEFUL_DAMAGE)
        if secs is None or secs > BREACH_MAX_S:
            return False                                          # не пробить или слишком долго
        self.intent = Intent.BREACH
        self._breach_wall = wall
        self._breach_point = point
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
        self._invalidate()                                        # стены уже нет: путь строим заново

    # ==========================================
    # ОГОНЬ
    # ==========================================

    def _gunnery(self, dt, me, enemy, ctx, aim_point):
        err = shortest_angle_diff(bearing_deg(me.x, me.y, *aim_point), me.turret_angle)
        breaching = self.intent is Intent.BREACH
        target = self._breach_wall if breaching else enemy
        # по врагу стреляем уже от 5% урона, по стене только от 15% (по этому порогу считалось время прорыва)
        min_frac = MIN_USEFUL_DAMAGE if breaching else NO_DAMAGE
        if abs(err) > 6.0:
            self._react_left = None
            return False

        info = compute_aim(me, ctx.targets)                       # то же, что видит игрок
        res = info.result
        if not (info.target is target and res is not None and res.damage_frac >= min_frac):
            self._react_left = None
            return False

        if self._react_left is None:                              # линия огня только что появилась
            self._react_left = self.rng.uniform(*self.skill.reaction)
        self._react_left -= dt
        return (self._react_left <= 0.0 and abs(err) <= FIRE_TOLERANCE_DEG
                and me.reload_left <= 0.0)