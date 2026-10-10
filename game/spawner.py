"""game/spawner.py — появление ботов: строго 1 танк за SPAWN_INTERVAL_S секунд."""
import math
import random

from engine import PX_PER_M
from vehicles import Tank, TankSpec
from ai import (Bot, BotBrain, DEFAULT_SKILL, ARCHETYPES, fit_loadout, BASE_BUDGET,
                threat_profile, counter_multipliers)

SPAWN_INTERVAL_S = 15.0
FIRST_SPAWN_S = 3.0
RETRY_S = 0.5                # если места не нашлось, пробуем снова через это время
BUDGET_PER_SPAWN = 0         # прибавка к бюджету за каждого уже появившегося бота
MAX_ALIVE = None             # None: без ограничения; число: слот пропускается, ритм не сбивается

SPAWN_MARGIN_M = 15.0        # запас за краем экрана
SPAWN_BAND_M = 30.0          # толщина кольца появления
FIND_RADIUS_M = 20.0         # насколько далеко от точки кольца искать свободное место
RING_TRIES = 6
SMART_SPAWN = True           # False: старое поведение, веса только из spawn_weight
EARLY_UNLOCK_FROM = 1        # с какого по счёту спавна контр-архетип может появиться раньше UNLOCKS
EARLY_UNLOCK_MULT = 1.8      # ...если его множитель шанса не ниже этого значения

# (с какого по счёту спавна, ключ архетипа): архетип входит в случайный выбор
UNLOCKS = [(0, "universal"), (2, "scout"), (4, "destroyer"), (6, "bunker")]

class BotSpawner:
    def __init__(self, fleet, finder, camera, seed):
        self.fleet = fleet
        self.finder = finder
        self.camera = camera
        self.rng = random.Random(seed + 777)
        self.spawned = 0
        self._clock = 0.0
        self._due = FIRST_SPAWN_S          # расписание: абсолютное время следующего спавна
        self._retry_at = 0.0
        self.profile = {}                  # последний профиль игрока (для отладочных строк)
        self.multipliers = {}              # последние множители шансов архетипов

    @property
    def time_left(self):
        return max(0.0, self._due - self._clock)

    def update(self, dt):
        if not self.fleet.player.alive:
            return
        self._clock += dt
        if self._clock < self._due or self._clock < self._retry_at:
            return
        if MAX_ALIVE is not None and len(self.fleet.bots) >= MAX_ALIVE:
            self._due += SPAWN_INTERVAL_S
            return
        if self._spawn():
            self.spawned += 1
            self._due += SPAWN_INTERVAL_S      # += а не «сейчас + 30»: ритм строгий
        else:
            self._retry_at = self._clock + RETRY_S

    def _spawn(self):
        arch = self._pick_archetype()
        budget = round((BASE_BUDGET + BUDGET_PER_SPAWN * self.spawned) * arch.budget_k)
        spec = TankSpec.from_values(fit_loadout(arch, budget, self.rng))
        tank = Tank(0.0, 0.0, spec=spec, team_color=arch.color, team="bots")

        player = self.fleet.player
        cam = self.camera
        inner = math.hypot(cam.view_w, cam.view_h) / 2.0 / cam.zoom + SPAWN_MARGIN_M * PX_PER_M
        outer = inner + SPAWN_BAND_M * PX_PER_M
        for _ in range(RING_TRIES):
            a = self.rng.uniform(0.0, 2.0 * math.pi)
            r = self.rng.uniform(inner, outer)
            px, py = player.x + math.cos(a) * r, player.y + math.sin(a) * r
            heading = math.degrees(math.atan2(player.y - py, player.x - px)) + 90.0
            spot = self.finder.find_near(tank, px, py, FIND_RADIUS_M, heading=heading, rng=self.rng)
            if spot is not None:
                tank.place_at(spot)
                self.fleet.bots.append(Bot(tank, BotBrain(arch, DEFAULT_SKILL, self.rng)))
                return True
        return False

    def _pick_archetype(self):
        """Случайный архетип: базовый вес умножается на множитель контр-выбора против текущего игрока."""
        if SMART_SPAWN:
            self.profile = threat_profile(self.fleet.player.spec)
            mult = counter_multipliers(self.profile, ARCHETYPES)
        else:
            self.profile = {}
            mult = {k: 1.0 for k in ARCHETYPES}
        self.multipliers = mult

        pool = [k for n, k in UNLOCKS
                if self.spawned >= n
                or (SMART_SPAWN and self.spawned >= EARLY_UNLOCK_FROM and mult[k] >= EARLY_UNLOCK_MULT)]
        weights = [ARCHETYPES[k].spawn_weight * mult[k] for k in pool]
        return ARCHETYPES[self.rng.choices(pool, weights=weights)[0]]