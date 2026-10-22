"""game/spawner.py — раунды: отсчёт, групповое появление ботов, смена раундов."""
import math
import random
from enum import Enum, auto

from engine import PX_PER_M, Team, bearing_deg
from vehicles import VEHICLE_TYPES, make_vehicle
from ai import (Bot, BotBrain, DEFAULT_SKILL, ARCHETYPES, fit_loadout,
                threat_profile, counter_multipliers)
from ai.loadout import loadout_cost
from ..control.camera import LOOK_MARGIN_PX
from .schedule import ROUND_TIME_S, COUNTDOWN_S, MAX_BOTS, round_budgets

RETRY_S = 0.5                # пауза между неудачными попытками найти место
SPAWN_MARGIN_M = 15.0        # запас за краем экрана
SPAWN_BAND_M = 30.0          # толщина кольца появления
FIND_RADIUS_M = 25.0         # насколько далеко от анкера искать место под каждый танк
RING_TRIES = 6               # попыток выбрать анкер за один заход
REPEAT_K = 0.5               # во сколько раз падает вес архетипа, уже выбранного в этой группе
EARLY_UNLOCK_ROUND = 2       # с какого раунда контр-архетип может появиться раньше расписания
EARLY_UNLOCK_MULT = 1.8      # ...если его множитель шанса не ниже этого значения

# (с какого раунда, ключ архетипа): архетип входит в случайный выбор
UNLOCKS = [(1, "universal"), (2, "scout"), (3, "destroyer"), (4, "bunker"),
           (5, "assault"), (6, "sniper")]

class RoundPhase(Enum):
    COUNTDOWN = auto()       # отсчёт, мигает указатель
    FIGHT = auto()           # группа на карте, идёт таймер раунда

class BotSpawner:
    def __init__(self, fleet, finder, camera, seed, prefs):
        self.fleet = fleet
        self.finder = finder
        self.camera = camera
        self.prefs = prefs
        self.rng = random.Random(seed + 777)

        self.round = 0                     # 0: игра ещё не началась (раунд 1 стартует в первом update)
        self.phase = RoundPhase.COUNTDOWN
        self.spawned = 0                   # сколько ботов появилось за всю партию
        self.anchor = None                 # точка появления группы (мировые px) или None
        self.profile = {}                  # профиль игрока (для отладочных строк)
        self.multipliers = {}              # множители шансов архетипов (для отладки)
        self.fit_info = "-"                # «Универсал 100%, Разведчик 99%»: попадание в бюджет

        self._clock = 0.0
        self._t = 0.0                      # время в текущей фазе
        self._retry_at = 0.0
        self._pending = []                 # [(архетип, танк)]: группа, ждущая появления
        self._group = []                   # [Bot]: группа текущего раунда

    # ---------- что читает интерфейс ----------
    @property
    def time_left(self):
        """COUNTDOWN: секунд до появления. FIGHT: секунд до конца раунда."""
        total = COUNTDOWN_S if self.phase is RoundPhase.COUNTDOWN else ROUND_TIME_S
        return max(0.0, total - self._t)

    @property
    def warning_visible(self):
        """Три вспышки по 0.5 с с паузами 0.5 с ровно за 3 секунды отсчёта."""
        return (self.phase is RoundPhase.COUNTDOWN and self.anchor is not None
                and self._t % 1.0 < 0.5)

    @property
    def group_total(self):
        return len(self._pending) if self.phase is RoundPhase.COUNTDOWN else len(self._group)

    @property
    def group_alive(self):
        return sum(1 for b in self._group if b.tank.alive)

    # ---------- кадр ----------
    def update(self, dt):
        if not self.fleet.player.alive:
            return
        if self.round == 0:
            self._begin_round(1)
        self._clock += dt
        self._t += dt

        if self.phase is RoundPhase.COUNTDOWN:
            if self._clock < self._retry_at:
                return
            if self.anchor is None:                       # анкер выбрать не удалось: пробуем снова
                if not self._pick_anchor():
                    self._retry_at = self._clock + RETRY_S
                return
            if self._t >= COUNTDOWN_S:
                if self._spawn_group():
                    self.phase = RoundPhase.FIGHT
                    self._t = 0.0
                else:
                    self._retry_at = self._clock + RETRY_S
                    self._pick_anchor()                   # вдруг повезёт с другим местом
        else:
            if self._t >= ROUND_TIME_S or self.group_alive == 0:
                self._begin_round(self.round + 1)

    # ---------- начало раунда ----------
    def _begin_round(self, n):
        self.round = n
        self.phase = RoundPhase.COUNTDOWN
        self._t = 0.0
        self._group = []
        self._pending = self._prepare_group()
        self.anchor = None
        if not self._pick_anchor():
            self._retry_at = self._clock + RETRY_S

    def _prepare_group(self):
        """Подбирает сборки группы по текущей цене танка игрока. Возвращает [(архетип, танк)]."""
        player = self.fleet.player
        value = player.spec.cost
        self.profile = threat_profile(player.spec)
        pool, mult = self._unlocked()

        picked, result, info = [], [], []
        for frac in round_budgets(self.round):
            key = self._pick_key(pool, mult, picked)
            picked.append(key)
            arch = ARCHETYPES[key]
            budget = value * frac
            values = fit_loadout(arch, budget, self.rng)
            spec = VEHICLE_TYPES[arch.kind].spec_cls.from_values(values, unbounded=True)
            tank = make_vehicle(arch.kind, spec, team_color=arch.color, team=Team.BOTS,
                                label=arch.name, emblem=arch.emblem)
            result.append((arch, tank))
            info.append(f"{arch.name} {loadout_cost(values) / budget * 100:.0f}%")
        self.fit_info = ", ".join(info)
        return result

    def _unlocked(self):
        """Открытые на этом раунде архетипы (только включённые в настройках) и их множители шансов."""
        allowed = self.prefs.enabled_keys()
        keys = [k for k in ARCHETYPES if k in allowed]
        mult = counter_multipliers(self.profile, keys)
        self.multipliers = mult
        ordered = [(n, k) for n, k in UNLOCKS if k in allowed]
        progress = self.round + ordered[0][0] - 1         # первый из включённых доступен с раунда 1
        pool = [k for n, k in ordered
                if progress >= n
                or (self.round >= EARLY_UNLOCK_ROUND and mult[k] >= EARLY_UNLOCK_MULT)]
        return pool, mult

    def _pick_key(self, pool, mult, picked):
        weights = [ARCHETYPES[k].spawn_weight * mult[k] * REPEAT_K ** picked.count(k)
                   for k in pool]
        return self.rng.choices(pool, weights=weights)[0]

    # ---------- точка появления ----------
    def _ring_radii(self):
        """Внутренний и внешний радиусы кольца за краем экрана, мировые px."""
        cam = self.camera
        half_diag = math.hypot(cam.view_w, cam.view_h) / 2.0
        look = math.hypot(max(0.0, cam.view_w / 2.0 - LOOK_MARGIN_PX),
                          max(0.0, cam.view_h / 2.0 - LOOK_MARGIN_PX))
        inner = (half_diag + look) / cam.zoom + SPAWN_MARGIN_M * PX_PER_M
        return inner, inner + SPAWN_BAND_M * PX_PER_M

    def _pick_anchor(self):
        """Выбирает анкер, где точно помещается самый крупный танк группы. True при успехе.
        Прежний анкер при неудаче не трогаем."""
        if not self._pending:
            return False
        probe = max((t for _, t in self._pending), key=lambda t: t.reach_px())
        player = self.fleet.player
        inner, outer = self._ring_radii()
        for _ in range(RING_TRIES):
            a = self.rng.uniform(0.0, 2.0 * math.pi)
            r = self.rng.uniform(inner, outer)
            x, y = player.x + math.cos(a) * r, player.y + math.sin(a) * r
            heading = bearing_deg(x, y, player.x, player.y)
            if self.finder.find_near(probe, x, y, FIND_RADIUS_M,
                                     heading=heading, rng=self.rng) is not None:
                self.anchor = (x, y)
                return True
        return False

    def _anchor_outside_screen(self):
        """За 3 секунды игрок мог подъехать (или отдалить камеру): выталкиваем анкер за экран по лучу."""
        player = self.fleet.player
        inner, _ = self._ring_radii()
        ax, ay = self.anchor
        dx, dy = ax - player.x, ay - player.y
        d = math.hypot(dx, dy)
        if d >= inner:
            return ax, ay
        if d < 1.0:
            dx, dy, d = 1.0, 0.0, 1.0
        k = inner / d
        return player.x + dx * k, player.y + dy * k

    # ---------- появление группы ----------
    def _spawn_group(self):
        """Ставит всю группу вокруг анкера. Если хоть один танк не поместился, откатывает и возвращает False."""
        if len(self.fleet.bots) + len(self._pending) > MAX_BOTS:
            return False                                  # на карте слишком много: ждём

        player = self.fleet.player
        ax, ay = self._anchor_outside_screen()
        self.anchor = (ax, ay)
        heading = bearing_deg(ax, ay, player.x, player.y)

        placed = []
        for arch, tank in self._pending:
            spot = self.finder.find_near(tank, ax, ay, FIND_RADIUS_M,
                                         heading=heading, rng=self.rng)
            if spot is None:
                ids = {id(b) for b in placed}
                self.fleet.bots = [b for b in self.fleet.bots if id(b) not in ids]
                return False
            tank.place_at(spot)
            brain = BotBrain(arch, DEFAULT_SKILL, random.Random(self.rng.random()))
            bot = Bot(tank, brain)
            self.fleet.bots.append(bot)                   # следующий танк увидит этот как препятствие
            placed.append(bot)

        self._group = placed
        self._pending = []
        self.spawned += len(placed)
        return True