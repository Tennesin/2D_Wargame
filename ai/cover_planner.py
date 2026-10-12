"""ai/cover_planner.py — поведение «спрятаться и ждать»: поездка к укрытию, ожидание, выход.
Само место укрытия ищет ai/cover.py. Команду (курс, газ) планировщик кладёт в поля heading и go."""
import math

from engine import PX_PER_M, bearing_deg
from .cover import find_cover, shield_between, attention
from .gunnery import best_hull_heading

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

class CoverPlanner:
    def __init__(self, nav):
        self.nav = nav
        self.heading = 0.0                  # результат step(): курс корпуса
        self.go = 0.0                       # и газ
        self._pt = None
        self._state = "move"                # "move" едем, "hold" ждём
        self._t = 0.0
        self._calm_t = 0.0
        self._hp0 = 0.0
        self._tries = 0
        self._cooldown = 0.0                # сколько секунд ещё нельзя идти в укрытие
        self._bad = []                      # [[x, y, ttl], ...] негодные укрытия

    # ---------- время и доступность ----------
    def tick(self, dt):
        if self._cooldown > 0.0:
            self._cooldown -= dt
        if self._bad:
            for s in self._bad:
                s[2] -= dt
            self._bad[:] = [s for s in self._bad if s[2] > 0.0]

    @property
    def available(self):
        return self._cooldown <= 0.0

    def block(self, seconds):
        """Запретить укрытия на seconds секунд."""
        self._cooldown = seconds

    # ---------- жизненный цикл ----------
    def begin(self, me, enemy, ctx):
        """Начать прятаться: ищем точку. False, если подходящей нет."""
        self._t = 0.0
        self._tries = 0
        self._calm_t = 0.0
        return self._pick(me, enemy, ctx)

    def _pick(self, me, enemy, ctx):
        spot = find_cover(me, enemy, ctx, self._bad)
        if spot is None:
            return False
        self._pt = spot
        self._state = "move"
        self.nav.invalidate()
        return True

    def step(self, me, enemy, ctx, dist, tick):
        """Один шаг укрытия. True: продолжаем прятаться (heading и go выставлены, либо остались прежними).
        False: вышли из укрытия (вызывающий меняет намерение)."""
        self._t += tick
        if self._t > COVER_MAX_S:
            return self._leave(COVER_COOLDOWN_S)

        cx, cy = self._pt
        d_pt = math.hypot(cx - me.x, cy - me.y)
        hidden = shield_between(ctx, enemy, me.x, me.y) is not None   # закрыт ли я прямо сейчас

        if self._state == "move":
            if hidden and d_pt <= COVER_HOLD_M * PX_PER_M:
                self._state = "hold"
                self._calm_t = 0.0
                self._hp0 = me.hp
            elif d_pt <= COVER_ARRIVE_M * PX_PER_M:
                return self._retry(me, enemy, ctx)                    # приехали, а тут не прикрыто
            else:
                self.heading, self.go = self.nav.drive_to(
                    me, ctx, (cx, cy), bearing_deg(me.x, me.y, cx, cy), no_breach=True)
                return True

        # состояние "hold"
        if not hidden or me.hp < self._hp0 - COVER_HP_DROP * me.max_hp:
            return self._retry(me, enemy, ctx)                        # игрок сместился, стена рухнула или бьют
        att = attention(enemy, me, [b.tank for b in ctx.fleet.bots])
        if att == "me":
            self._calm_t = 0.0
            if dist < COVER_PANIC_M * PX_PER_M:
                return self._leave(COVER_FIGHT_S)                     # прижали: драться
        else:
            self._calm_t += tick * (2.0 if att == "other" else 1.0)  # игрок занят другим
            if self._calm_t >= COVER_CALM_S:
                return self._leave(COVER_COOLDOWN_S)
        self.heading = best_hull_heading(me, enemy, bearing_deg(me.x, me.y, enemy.x, enemy.y))
        self.go = 0.0
        return True

    def _retry(self, me, enemy, ctx):
        """Это укрытие не работает: запоминаем его и текущую точку как плохие и ищем другое."""
        cx, cy = self._pt
        self._bad.append([cx, cy, COVER_BAD_S])
        self._bad.append([me.x, me.y, COVER_BAD_S])
        self._tries += 1
        if self._tries >= COVER_MAX_TRIES or not self._pick(me, enemy, ctx):
            return self._leave(COVER_FIGHT_S)
        return True

    def _leave(self, cooldown):
        """Выход из укрытия. Всегда возвращает False (удобно для step)."""
        self._pt = None
        self._cooldown = cooldown
        self.nav.invalidate()
        return False