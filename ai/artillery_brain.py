"""ai/artillery_brain.py — мозг САУ: держать дистанцию, отходить из мёртвой зоны, бить по упреждённой точке.
Тот же интерфейс, что у BotBrain: think(dt, me, enemy, ctx) -> VehicleCommand."""
import math
from enum import Enum, auto

from engine import VehicleCommand, WORLD, PX_PER_M, TAU, clamp, bearing_deg
from .gunnery import lead_point
from .navigator import Navigator
from .steering import steer_to, StuckGuard

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
WORLD_MARGIN_M = 8.0     # путевые точки не ставим ближе этого к краю мира
READY_S = 2.0            # перезарядка кончается меньше чем через столько секунд: считаем орудие готовым
HOLD_MIN_S = 1.0         # минимальное время удержания намерения (против дрожания решений)

# --- огонь ---
FIRE_MIN_K = 1.05        # стреляем, только если точка упреждения дальше мёртвой зоны * этого
FIRE_MAX_K = 0.98        # и ближе максимальной дальности * этого
SCATTER_K = 0.05         # разброс падения: доля дистанции до точки (при 112 м около 5.6 м)

class ArtilleryBrain:
    def __init__(self, arch, skill, rng):
        self.arch, self.skill, self.rng = arch, skill, rng
        self.intent = ArtyIntent.POSITION          # BotBrain._pick_flank_side читает intent у соседей
        self.stuck = StuckGuard()
        self.nav = Navigator(rng)
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
        """ctx — BotContext (нужны targets не нужны, но budget и nav нужны навигатору)."""
        if not enemy.alive:
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

        throttle, steer = steer_to(me, heading, self._go)
        pushing = (throttle != 0.0 or steer != 0.0) and not me.stunned
        reversing = self.stuck.update(dt, me, pushing, self.rng)
        if reversing:
            if not self._was_reversing:
                self.nav.remember_stuck(me)
            throttle, steer = -1.0, self.stuck.turn
        self._was_reversing = reversing

        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim,
                              fire=self._can_fire(me, aim))

    # ==========================================
    # РЕШЕНИЕ
    # ==========================================
    def _decide(self, me, enemy, ctx):
        spec = me.spec
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
        if self.intent is ArtyIntent.RETREAT:
            step = RETREAT_STEP_M * PX_PER_M
            goal = self._inside_world(me.x + ux * step, me.y + uy * step)
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

    @staticmethod
    def _can_fire(me, aim):
        """Просим огонь, только если точка упреждения в допустимом кольце. Остальное
        (перезарядка, оглушение, довод орудия) проверяет сама ArtilleryVehicle._try_fire."""
        if me.stunned:
            return False
        spec = me.spec
        d = math.hypot(aim[0] - me.x, aim[1] - me.y)
        return spec.RANGE_MIN_PX * FIRE_MIN_K <= d <= spec.RANGE_MAX_PX * FIRE_MAX_K