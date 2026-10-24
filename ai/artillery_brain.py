"""ai/artillery_brain.py — мозг САУ: держать дистанцию, отходить из мёртвой зоны, бить по упреждённой точке.
Не стреляет, если фугас накроет союзника (при включённом friendly_fire).
Тот же интерфейс, что у BotBrain: think(dt, me, enemy, ctx) -> VehicleCommand."""
import math
from enum import Enum, auto

from engine import VehicleCommand, WORLD, PX_PER_M, TAU, clamp, bearing_deg, heading_vector
from .tactics.gunnery import lead_point
from .team.hazards import friendly_fire_on
from .movement.navigator import Navigator
from .movement.steering import steer_to, StuckGuard
from .team.avoidance import AllyAvoider

class ArtyIntent(Enum):
    POSITION = auto()    # ехать на выгодную дистанцию
    FIRE = auto()        # стоять и стрелять
    RETREAT = auto()     # игрок слишком близко: уезжать

# --- дистанции: доли максимальной дальности и мёртвой зоны ---
HOLD_K = 0.70            # желаемая дистанция до игрока
NEAR_K = 0.55            # ближе этого и перезарядка идёт: отъезжаем
FAR_K = 0.85             # дальше этого: подъезжаем
RETREAT_ENTER_K = 1.4    # игрок ближе мёртвой зоны * этого: бежим
RETREAT_EXIT_K = 2.2     # убежали дальше мёртвой зоны * этого: можно снова воевать
RETREAT_STEP_M = 30.0    # на сколько метров вперёд ставим точку отхода
RETREAT_TURN_COST_M = 0.15   # «цена» одного градуса отклонения от прямого отхода, м
WORLD_MARGIN_M = 8.0     # путевые точки не ставим ближе этого к краю мира
READY_S = 2.0            # перезарядка кончается меньше чем через столько секунд: считаем орудие готовым
HOLD_MIN_S = 1.0         # минимальное время удержания намерения (против дрожания решений)

# --- огонь ---
FIRE_MIN_K = 1.05        # стреляем, только если точка упреждения дальше мёртвой зоны * этого
FIRE_MAX_K = 0.98        # и ближе максимальной дальности * этого
SCATTER_K = 0.05         # разброс падения: доля дистанции до точки (при 112 м около 5.6 м)

# --- свои под ударом ---
ALLY_MARGIN_M = 2.0      # запас вокруг взрыва, внутри которого союзник считается под ударом
PREDICT_CAP_S = 3.0      # дальше этого вперёд движение союзника не предсказываем
PENDING_S = 1.5          # орудие готово меньше чем через столько секунд: зона считается «собирается»

class ArtilleryBrain:
    def __init__(self, arch, skill, rng):
        self.arch, self.skill, self.rng = arch, skill, rng
        self.intent = ArtyIntent.POSITION          # BotBrain._pick_flank_side читает intent у соседей
        self.stuck = StuckGuard()
        self.avoid = AllyAvoider()
        self.nav = Navigator(rng)
        self.pending_zone = None                   # (x, y, радиус) места, куда САУ вот-вот выстрелит; читает HazardBoard
        self.hold_reason = ""                      # "ally": не стреляю, чтобы не задеть своих (для отладки)
        self._hold = 0.0
        self._think_in = rng.uniform(0.0, 1.0 / skill.think_hz)   # сдвиг фаз между ботами
        self._heading, self._go = 0.0, 0.0
        self._was_reversing = False
        self._prev_since = 999.0                   # since_shot в прошлом кадре: по скачку вниз видим выстрел
        self._sx = self._sy = 0.0                  # единичный случайный вектор разброса текущего выстрела
        self._roll_scatter()

    # ==========================================
    # КАДР
    # ==========================================
    def think(self, dt, me, enemy, ctx):
        """ctx — BotContext (targets не нужны, но budget, nav и fleet нужны)."""
        if not enemy.alive:
            self.pending_zone = None
            return VehicleCommand()

        self._hold -= dt
        self._think_in -= dt
        self.nav.tick(dt)
        self._track_shot(me)
        if self._think_in <= 0.0:                                 # редко: решения и поиск пути
            self._think_in += 1.0 / self.skill.think_hz
            self._decide(me, enemy, ctx)

        aim = self._aim_point(me, enemy)                          # каждый кадр: дёшево

        # Стоим на месте: орудие без башни, поэтому доворачиваем КОРПУС, пока цель не войдёт в сектор
        heading = self._heading
        if self._go == 0.0:
            off = me.hull_offset_to(*aim)
            heading = me.hull_angle + off if off != 0.0 else me.hull_angle

        heading, go = self.avoid.adjust(dt, me, heading, self._go, ctx)
        throttle, steer = steer_to(me, heading, go)
        pushing = (throttle != 0.0 or steer != 0.0) and not me.stunned
        reversing = self.stuck.update(dt, me, pushing, self.rng)
        if reversing:
            if not self._was_reversing:
                self.nav.remember_stuck(me)
            throttle, steer = -1.0, self.stuck.turn
        self._was_reversing = reversing

        fire = self._can_fire(me, aim, ctx)
        self._update_pending(me, aim, fire)
        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim, fire=fire)

    # ==========================================
    # РЕШЕНИЕ
    # ==========================================
    def _decide(self, me, enemy, ctx):
        spec = me.spec

        # зона чужого снаряда: сначала выбираемся из неё
        board = ctx.hazards
        exit_pt = board.escape_point(me) if board is not None and not me.stunned else None
        if exit_pt is not None:
            want = bearing_deg(me.x, me.y, *exit_pt)
            heading, go = self.nav.drive_to(me, ctx, exit_pt, want, no_breach=True)
            self._heading, self._go = (want, 1.0) if go == 0.0 else (heading, go)
            return

        dx, dy = me.x - enemy.x, me.y - enemy.y          # вектор ОТ игрока КО МНЕ
        dist = math.hypot(dx, dy)

        intent = self._choose(me, dist)
        if intent is not self.intent:
            self.intent = intent
            self._hold = HOLD_MIN_S
            self.nav.invalidate()

        if self.intent is ArtyIntent.FIRE:
            self._heading, self._go = me.hull_angle, 0.0
            return

        ux, uy = (dx / dist, dy / dist) if dist > 1.0 else (0.0, 1.0)
        squad = getattr(ctx, "squad", None)
        slot = squad.slot(self) if squad is not None else None
        if slot is not None and self.intent is ArtyIntent.POSITION:
            ux, uy = heading_vector(slot)
        if self.intent is ArtyIntent.RETREAT:
            goal = self._retreat_goal(me, enemy, ux, uy)
        else:
            hold = spec.RANGE_MAX_PX * HOLD_K
            goal = self._inside_world(enemy.x + ux * hold, enemy.y + uy * hold)

        want = bearing_deg(me.x, me.y, *goal)
        # стены для САУ глухие (no_breach): ломать их нечем, фугас не пробивает
        self._heading, self._go = self.nav.drive_to(me, ctx, goal, want, no_breach=True)

    def _choose(self, me, dist):
        spec = me.spec
        dead, reach = spec.RANGE_MIN_PX, spec.RANGE_MAX_PX

        # бегство с гистерезисом: входим при 1.4 мёртвой зоны, выходим при 2.2
        if self.intent is ArtyIntent.RETREAT:
            if dist <= dead * RETREAT_EXIT_K:
                return ArtyIntent.RETREAT
        elif dist < dead * RETREAT_ENTER_K:
            return ArtyIntent.RETREAT

        if self._hold > 0.0 and self.intent is not ArtyIntent.RETREAT:
            return self.intent

        if dist > reach * FAR_K:
            return ArtyIntent.POSITION
        if dist >= reach * NEAR_K:
            return ArtyIntent.FIRE
        # близко, но ещё не опасно: если орудие почти готово, стреляем, иначе отходим на позицию
        return ArtyIntent.FIRE if me.reload_left <= READY_S else ArtyIntent.POSITION

    @staticmethod
    def _inside_world(x, y):
        mx = WORLD.half_w_px - WORLD_MARGIN_M * PX_PER_M
        my = WORLD.half_h_px - WORLD_MARGIN_M * PX_PER_M
        return clamp(x, -mx, mx), clamp(y, -my, my)

    def _retreat_goal(self, me, enemy, ux, uy):
        """Куда отходить. Прямо от игрока; если там край мира (САУ в углу), то вбок:
        выбираем точку, максимально далёкую от игрока, с небольшим штрафом за поворот."""
        step = RETREAT_STEP_M * PX_PER_M
        best, best_score = None, None
        for deg in (0.0, 45.0, -45.0, 90.0, -90.0):
            a = math.radians(deg)
            c, s = math.cos(a), math.sin(a)
            dx, dy = ux * c - uy * s, ux * s + uy * c
            gx, gy = self._inside_world(me.x + dx * step, me.y + dy * step)
            score = math.hypot(gx - enemy.x, gy - enemy.y) - abs(deg) * RETREAT_TURN_COST_M * PX_PER_M
            if best_score is None or score > best_score:
                best, best_score = (gx, gy), score
        return best

    # ==========================================
    # ОГОНЬ
    # ==========================================
    def _roll_scatter(self):
        ang = self.rng.uniform(0.0, TAU)
        rad = math.sqrt(self.rng.random())                        # равномерно по площади круга
        self._sx, self._sy = math.cos(ang) * rad, math.sin(ang) * rad

    def _track_shot(self, me):
        """Выстрел виден по сбросу since_shot: на новый выстрел бросаем новый разброс
        (в течение одного выстрела он не меняется, иначе орудие дёргалось бы)."""
        if me.since_shot < self._prev_since:
            self._roll_scatter()
        self._prev_since = me.since_shot

    def _aim_point(self, me, enemy):
        """Точка на земле: упреждение по скорости полёта снаряда плюс разброс, растущий с дистанцией."""
        px, py = lead_point(me, enemy, self.skill.lead_k)
        spread = math.hypot(px - me.x, py - me.y) * SCATTER_K
        return px + self._sx * spread, py + self._sy * spread

    def _can_fire(self, me, aim, ctx):
        """Просим огонь, только если точка в допустимом кольце и взрыв не заденет своих.
        Остальное (перезарядка, оглушение, довод орудия) проверяет ArtilleryVehicle._try_fire."""
        self.hold_reason = ""
        if me.stunned:
            return False
        spec = me.spec
        d = math.hypot(aim[0] - me.x, aim[1] - me.y)
        if not (spec.RANGE_MIN_PX * FIRE_MIN_K <= d <= spec.RANGE_MAX_PX * FIRE_MAX_K):
            return False
        if self._ally_in_blast(me, aim, d, ctx):
            self.hold_reason = "ally"
            return False
        return True

    @staticmethod
    def _ally_in_blast(me, aim, dist, ctx):
        """Заденет ли взрыв в точке aim союзника. Снаряд падает ровно в aim (тот же кадр, что и выстрел),
        поэтому разброс учитывать не нужно. Союзник проверяется сейчас и по ходу полёта снаряда
        (его движение предсказывается не дальше PREDICT_CAP_S)."""
        if not friendly_fire_on(ctx):
            return False
        stats = me.spec.shell_stats
        flight = min(dist / stats.speed_px, PREDICT_CAP_S)
        danger = stats.outer_radius_px + ALLY_MARGIN_M * PX_PER_M
        for b in ctx.fleet.bots:
            ally = b.tank
            if ally is me or not ally.alive:
                continue
            vx, vy = ally.velocity_px()
            reach = danger + ally.spec.HULL_REACH_PX
            for f in (0.0, 0.5, 1.0):
                t = flight * f
                if math.hypot(aim[0] - (ally.x + vx * t), aim[1] - (ally.y + vy * t)) < reach:
                    return True
        return False

    def _update_pending(self, me, aim, can_fire):
        """Публикуем «зону, куда я сейчас выстрелю»: боты снаружи не полезут туда, пока снаряд не полетит."""
        ready = can_fire and self.intent is ArtyIntent.FIRE and me.reload_left <= PENDING_S
        if not ready:
            self.pending_zone = None
            return
        d = math.hypot(aim[0] - me.x, aim[1] - me.y)
        self.pending_zone = (aim[0], aim[1], me.spec.shell_stats.outer_radius_px + d * SCATTER_K)