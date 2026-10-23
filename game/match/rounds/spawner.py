"""game/match/rounds/spawner.py — раунды: отсчёт, групповое появление ботов, смена раундов."""
import math
import random
from enum import Enum, auto

from engine import PX_PER_M, bearing_deg, SEED_SALT, WORLD
from ai import Bot, BotBrain, DEFAULT_SKILL
from ...config import LOOK_MARGIN_PX
from .composer import GroupComposer
from .schedule import ROUND_TIME_S, COUNTDOWN_S, MAX_BOTS

RETRY_S = 0.5                # пауза между неудачными попытками найти место
SPAWN_MARGIN_M = 15.0        # запас за краем экрана
SPAWN_BAND_M = 30.0          # толщина кольца появления
FIND_RADIUS_M = 25.0         # насколько далеко от анкера искать место под каждый танк
RING_TRIES = 6               # попыток выбрать анкер за один заход
FALLBACK_INSET_M = 12.0      # на сколько внутрь от границы мира ставится запасной анкер
FALLBACK_TRIES = 4           # случайных точек на каждую сторону мира в запасном плане

class RoundPhase(Enum):
    COUNTDOWN = auto()       # отсчёт, мигает указатель
    FIGHT = auto()           # группа на карте, идёт таймер раунда

class BotSpawner:
    def __init__(self, fleet, finder, camera, seed, prefs):
        self.fleet = fleet
        self.finder = finder
        self.camera = camera
        self.rng = random.Random(seed + SEED_SALT["spawner"])
        self.composer = GroupComposer(prefs, self.rng)

        self.round = 0                     # 0: игра ещё не началась (раунд 1 стартует в первом update)
        self.phase = RoundPhase.COUNTDOWN
        self.spawned = 0                   # сколько ботов появилось за всю партию
        self.anchor = None                 # точка появления группы (мировые px) или None
        self.anchor_is_fallback = False    # анкер выбран запасным планом (у границы мира)

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

    @property
    def profile(self):
        return self.composer.profile

    @property
    def multipliers(self):
        return self.composer.multipliers

    @property
    def fit_info(self):
        return self.composer.fit_info

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
        self._pending = self.composer.compose(n, self.fleet.player)
        self.anchor = None
        self.anchor_is_fallback = False
        if not self._pick_anchor():
            self._retry_at = self._clock + RETRY_S

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
        Основной план: кольцо за краем экрана. Запасной: у самой дальней от игрока границы мира
        (обзор настолько большой, что кольцо вылезло за карту, или места в кольце не нашлось).
        Прежний анкер при неудаче не трогаем."""
        if not self._pending:
            return False
        probe = max((t for _, t in self._pending), key=lambda t: t.reach_px())
        player = self.fleet.player
        inner, outer = self._ring_radii()
        if inner <= self._far_corner_dist(player):        # хоть какая-то часть кольца лежит внутри мира
            for _ in range(RING_TRIES):
                a = self.rng.uniform(0.0, 2.0 * math.pi)
                r = self.rng.uniform(inner, outer)
                x, y = player.x + math.cos(a) * r, player.y + math.sin(a) * r
                heading = bearing_deg(x, y, player.x, player.y)
                if self.finder.find_near(probe, x, y, FIND_RADIUS_M,
                                         heading=heading, rng=self.rng) is not None:
                    self.anchor = (x, y)
                    self.anchor_is_fallback = False
                    return True
        return self._pick_fallback_anchor(probe, player)

    @staticmethod
    def _far_corner_dist(player):
        """Расстояние от игрока до самого дальнего угла мира, px."""
        return math.hypot(WORLD.half_w_px + abs(player.x), WORLD.half_h_px + abs(player.y))

    def _pick_fallback_anchor(self, probe, player):
        """Запасной план: стороны мира перебираются от самой дальней от игрока к ближней.
        На стороне берётся несколько случайных точек, проверяются от самой дальней к ближней."""
        hw, hh = WORLD.half_w_px, WORLD.half_h_px
        inset = FALLBACK_INSET_M * PX_PER_M
        sides = sorted((("right", hw - player.x), ("left", hw + player.x),
                        ("bottom", hh - player.y), ("top", hh + player.y)),
                       key=lambda s: s[1], reverse=True)
        for side, _ in sides:
            candidates = []
            for _ in range(FALLBACK_TRIES):
                if side in ("left", "right"):
                    x = hw - inset if side == "right" else -hw + inset
                    y = self.rng.uniform(-hh + inset, hh - inset)
                else:
                    y = hh - inset if side == "bottom" else -hh + inset
                    x = self.rng.uniform(-hw + inset, hw - inset)
                candidates.append((x, y))
            candidates.sort(key=lambda p: (p[0] - player.x) ** 2 + (p[1] - player.y) ** 2,
                            reverse=True)
            for x, y in candidates:
                heading = bearing_deg(x, y, player.x, player.y)
                if self.finder.find_near(probe, x, y, FIND_RADIUS_M,
                                         heading=heading, rng=self.rng) is not None:
                    self.anchor = (x, y)
                    self.anchor_is_fallback = True
                    return True
        return False

    def _anchor_outside_screen(self):
        """За 3 секунды игрок мог подъехать (или отдалить камеру): выталкиваем анкер за экран по лучу."""
        if self.anchor_is_fallback:
            return self.anchor
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