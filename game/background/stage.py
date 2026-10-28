"""game/background/stage.py — «сцена» фона: камера, случайный кусок карты, актёры, эффекты
и API, которым пользуются события. Урона и столкновений нет: снаряды только взрываются на корпусах."""
import math
import random
from types import SimpleNamespace

from ai import BotContext, PlanBudget, TerrainNavCache
from combat import EffectsSystem, TargetSet
from world import Camera, ZOOM_LEVELS, WorldGenerator, TerrainMap, SpawnFinder, build_natural
from engine import PX_PER_M, Shot, WORLD, bearing_deg
from structures import WallManager
from vehicles.chassis.params import KMH_TO_PX

from ..hud.artillery_warning import ArtilleryWarning
from ..view.world_renderer import Renderer
from .actors import Actor
from .casting import Casting

SPAN = 1.9                       # во сколько раз рабочая область (с запасом за экраном) шире экрана
SPOT_SPAN = 1.6                  # область, в которой не должно быть глубокой воды
ZOOM_CHOICES = (7, 8, 8, 9)      # ступени зума камеры (случайно при каждой смене участка)
SPOT_TRIES = 8                   # сколько участков пробуем, пока не найдём без глубокой воды
SPAWN_SEARCH_M = 25.0            # в каком радиусе ищем свободное место под появляющуюся технику
ARTY_ORIGIN_FY = 1.06            # откуда «стреляет» невидимая артиллерия: чуть ниже экрана

class _Crowd:
    """Источник целей для снарядов (тот же интерфейс, что у Fleet): снаряд рвётся на корпусе
    чужой команды. Своих снаряд не задевает."""

    def __init__(self, actors):
        self._actors = actors

    @property
    def vehicles(self):
        return [a.v for a in self._actors]

    @property
    def bots(self):
        """Навигатору нужен список с полем .tank у каждого элемента (у Actor оно есть)."""
        return self._actors

    def obbs_near(self, me, radius):
        """Прямоугольники чужой техники рядом с me: препятствия для me (как Fleet.obbs_near)."""
        result = []
        for a in self._actors:
            t = a.v
            if t is me or not t.alive:
                continue
            reach = radius + t.reach_px()
            dx, dy = t.x - me.x, t.y - me.y
            if dx * dx + dy * dy <= reach * reach:
                result.extend(t.footprint_at(t.x, t.y, t.hull_angle))
        return result

    def blocks_obb(self, obb):
        """Задевает ли прямоугольник хоть одну живую машину (для SpawnFinder)."""
        return any(a.v.hits_obb(obb) for a in self._actors if a.v.alive)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        team = getattr(ignore, "team", None)
        best = None
        for a in self._actors:
            t = a.v
            if not t.alive or t is ignore or (team is not None and t.team == team):
                continue
            res = t.raycast(x0, y0, x1, y1)
            if res is not None and (best is None or res[1] < best[1]):
                best = res
        return best

class Stage:
    def __init__(self, session, size, preload=True):
        self.rng = random.Random()
        self.casting = Casting(session, self.rng)
        self.size = size
        self.camera = Camera(*size)
        self.actors = []
        self.walls = WallManager()               # пустой: нужен Renderer
        self.effects = EffectsSystem()
        self.crowd = _Crowd(self.actors)
        self.warning = ArtilleryWarning(self.effects, self.camera)
        self.seed = None
        self.terrain = None
        self.renderer = None
        self.budget = PlanBudget(2)              # сколько путей A* можно строить за кадр на всех
        self.nav = None
        self.nav_ctx = None
        self.targets = None
        self._new_world()
        self.relocate(preload=preload)

    # ==========================================
    # МИР И КАМЕРА
    # ==========================================
    def _new_world(self):
        self.seed = self.rng.randrange(1, 1_000_000)
        self.terrain = TerrainMap(build_natural(self.seed, WORLD.width_m, WORLD.height_m))
        self.nav = TerrainNavCache(self.terrain)
        self.targets = TargetSet(self.terrain, self.crowd)   # камни останавливают и снаряды
        self.nav_ctx = BotContext(targets=self.targets, terrain=self.terrain, walls=self.walls,
                                  fleet=self.crowd, budget=self.budget, nav=self.nav)
        ctx = SimpleNamespace(terrain=self.terrain, fleet=self.crowd,
                              walls=self.walls, effects=self.effects)
        self.renderer = Renderer(WorldGenerator(self.seed), ctx)

    def _extent(self, span):
        """Половина области шириной span экранов вокруг центра камеры, мировые px: (по X, по Y)."""
        w, h = self.size
        z = self.camera.zoom
        return w / z * span / 2.0, h / z * span / 2.0

    def _fit_zoom(self):
        cam = self.camera
        cam.zoom_by(self.rng.choice(ZOOM_CHOICES) - cam.zoom_level)
        while cam.zoom_level < len(ZOOM_LEVELS) - 1:
            ex, ey = self._extent(SPAN)
            if ex <= WORLD.half_w_px and ey <= WORLD.half_h_px:
                break
            cam.zoom_by(1)                       # мир мал для этого окна: приближаем

    def _spot_ok(self):
        """В области кадра нет глубокой воды."""
        cx, cy = self.camera.x, self.camera.y
        ex, ey = self._extent(SPOT_SPAN)
        grid = self.terrain.grid
        i0, i1, j0, j1 = grid.cell_range(cx - ex, cy - ey, cx + ex, cy + ey)
        return not grid.has_deep_in(i0, i1, j0, j1)

    def relocate(self, new_world=False, preload=True):
        """Новый случайный участок карты (и при new_world новая карта). Звать, пока экран чёрный."""
        if new_world:
            self._new_world()
        for _ in range(SPOT_TRIES):
            self._fit_zoom()
            ex, ey = self._extent(SPAN)
            mx = max(0.0, WORLD.half_w_px - ex)
            my = max(0.0, WORLD.half_h_px - ey)
            self.camera.center_on(self.rng.uniform(-mx, mx), self.rng.uniform(-my, my))
            if self._spot_ok():
                break
        if preload:
            self.renderer.preload(self.camera)

    def resize(self, size):
        self.size = size
        self.camera.resize(*size)

    # ==========================================
    # API ДЛЯ СОБЫТИЙ
    # ==========================================
    def pt(self, fx, fy):
        """Точка экрана в долях -> мировые px."""
        w, h = self.size
        return self.camera.screen_to_world(fx * w, fy * h)

    def frac(self, wx, wy):
        """Мировые px -> доли экрана."""
        sx, sy = self.camera.world_to_screen(wx, wy)
        return sx / self.size[0], sy / self.size[1]

    def route(self, points):
        """Список точек в долях экрана -> список мировых точек для Actor.drive."""
        return [self.pt(*p) for p in points]

    def kmh(self, widths_per_s):
        """Скорость в ширинах экрана в секунду -> км/ч (так события не зависят от зума и окна)."""
        return widths_per_s * self.size[0] / self.camera.zoom / KMH_TO_PX

    def _add(self, vehicle, at, heading):
        x, y = self.pt(*at)
        vehicle.x, vehicle.y = x, y
        vehicle.hull_angle = heading % 360.0
        # ищем свободное место рядом: не внутри камня, воды или другого танка
        finder = SpawnFinder(self.terrain, blockers=[self.crowd.blocks_obb])
        spot = finder.find_near(vehicle, x, y, SPAWN_SEARCH_M, heading=heading, rng=self.rng)
        if spot is not None:
            vehicle.place_at(spot)
        actor = Actor(self, vehicle)
        self.actors.append(actor)
        return actor

    def spawn_player(self, at, heading=0.0):
        """Танк игрока (собранный в конструкторе) в точке at (доли экрана)."""
        return self._add(self.casting.player(), at, heading)

    def spawn_bot(self, key, at, heading=0.0, budget_k=0.7):
        """Бот архетипа key ("universal", "scout", "assault"...)."""
        return self._add(self.casting.bot(key, budget_k), at, heading)

    def remove(self, actor):
        actor.removed = True
        if actor in self.actors:
            self.actors.remove(actor)

    # ---------- артиллерия ----------
    def fire_artillery(self, target, origin=None, cal=200):
        """Выстрел невидимой САУ в точку target (мировые px). Возвращает время полёта, с."""
        spec = self.casting.arty_spec(cal)
        if origin is None:
            origin = self.pt(self.rng.uniform(0.05, 0.95), ARTY_ORIGIN_FY)
        ox, oy = origin
        tx, ty = target
        stats = spec.shell_stats
        shot = Shot(ox, oy, bearing_deg(ox, oy, tx, ty), stats, target=(tx, ty))
        self.effects.spawn_shot(shot, spec, None)
        return math.hypot(tx - ox, ty - oy) / stats.speed_px

    def shell_at(self, actor, scatter_m=6.0, cal=200):
        """Снаряд САУ по упреждённой точке перед техникой actor, с разбросом scatter_m (близкий промах)."""
        spec = self.casting.arty_spec(cal)
        ox, oy = self.pt(self.rng.uniform(0.05, 0.95), ARTY_ORIGIN_FY)
        v = actor.v
        vx, vy = v.velocity_px()
        speed = spec.shell_stats.speed_px
        t = math.hypot(v.x - ox, v.y - oy) / speed
        tx, ty = v.x, v.y
        for _ in range(2):
            tx, ty = v.x + vx * t, v.y + vy * t
            t = math.hypot(tx - ox, ty - oy) / speed
        a = self.rng.uniform(0.0, math.tau)
        r = scatter_m * PX_PER_M * math.sqrt(self.rng.random())
        return self.fire_artillery((tx + math.cos(a) * r, ty + math.sin(a) * r), (ox, oy), cal)

    def jittered_grid(self, cols, rows, cover=0.9, jitter=0.35):
        """Точки (мировые px) по сетке cols x rows на cover доли экрана, со случайным сдвигом, в случайном порядке."""
        x0 = y0 = 0.5 - cover / 2.0
        cw, ch = cover / cols, cover / rows
        pts = []
        for r in range(rows):
            for c in range(cols):
                fx = x0 + (c + 0.5 + self.rng.uniform(-jitter, jitter)) * cw
                fy = y0 + (r + 0.5 + self.rng.uniform(-jitter, jitter)) * ch
                pts.append(self.pt(fx, fy))
        self.rng.shuffle(pts)
        return pts

    # ---------- условия ожидания (для yield) ----------
    @staticmethod
    def all_done(*actors):
        """yield stage.all_done(a, b): ждать, пока все перечисленные актёры закончат маршрут."""
        return lambda: all(a.is_done() for a in actors)

    def empty(self):  # запас API: события пока не используют
        return not self.actors

    def quiet(self):
        """Нет актёров, летящих снарядов и взрывов (дым и копоть догорают сами)."""
        e = self.effects
        return not (self.actors or e.shells or e.artillery_shells or e.explosions)

    # ==========================================
    # КАДР
    # ==========================================
    def update(self, dt):
        self.budget.new_frame()
        for actor in self.actors:
            v = actor.v
            obstacles = self.crowd.obbs_near(v, v.reach_px())
            shot = v.update(actor.command(dt), dt, obstacles, self.terrain)
            if shot is not None:
                self.effects.spawn_shot(shot, v.spec, v)
                actor.on_shot()
        self.effects.update(dt, self.targets)    # попадания, рикошеты, промахи игнорируем: урона нет
        self._reap()

    def _reap(self):
        if not self.actors:
            return
        keep = []
        for a in self.actors:
            if ((a.done or a.retired) and a.offscreen()) or a.far_away():
                a.removed = True
            else:
                keep.append(a)
        self.actors[:] = keep                    # тот же список, что у _Crowd

    def clear(self):
        """Убрать всех актёров и все эффекты (при смене участка карты, пока экран чёрный)."""
        for a in self.actors:
            a.removed = True
        self.actors.clear()
        e = self.effects
        for name in ("shells", "artillery_shells", "flashes", "smoke", "explosions", "scorches", "sparks"):
            getattr(e, name).clear()

    def draw(self, screen):
        self.renderer.draw(screen, self.camera)
        self.warning.draw(screen)