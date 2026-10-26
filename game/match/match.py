"""game/match/match.py — одна партия: мир, техника, режимы, контроллеры и порядок кадра.
Ничего не рисует и про интерфейс (панели, кнопки) не знает: всё нужное приходит снаружи.
notifier — приёмник сообщений о бое (его показывает hud, а партия только вызывает его методы)."""
from combat import EffectsSystem, TargetSet
from inputs import Action
from structures import WallManager
from world import TerrainMap, SpawnFinder, WorldBoundary

from .context import GameContext
from ..state.stats import MatchStats
from .fleet import Fleet
from .modes import Modes
from .control.bots import BotController
from .control.camera import CameraController
from .control.clicks import ClickRouter
from .control.hits import CombatController
from .control.player import TankController
from .control.ram import RamController
from .rounds.spawner import BotSpawner
from ..editor.mapio import load_walls

PLAYER_SEARCH_M = 40.0       # в каком радиусе от центра ищем место для танка игрока

class Match:
    def __init__(self, map_data, player, camera, input_handler, notifier, prefs, settings, on_exit):
        self.map_data = map_data
        self.seed = map_data.seed
        self.camera = camera
        self.input = input_handler
        self._on_exit = on_exit
        self._death_handled = False

        # --- данные ---
        self.terrain = TerrainMap(map_data)
        self.walls = WallManager()
        self._load_walls(map_data)
        self.fleet = Fleet(player)
        self._place_player(player)
        self.stats = MatchStats(player)
        self.ctx = GameContext(
            camera=camera, terrain=self.terrain, walls=self.walls, fleet=self.fleet,
            effects=EffectsSystem(), targets=TargetSet(self.walls, self.terrain, self.fleet, WorldBoundary()),
            notifier=notifier, settings=settings, match_stats=self.stats
        )

        # --- контроллеры игрока ---
        self.modes = Modes(input_handler)
        self.modes.on_exit = on_exit
        self.camera_ctrl = CameraController(camera, input_handler)
        self.combat = CombatController(self.ctx, self.modes)
        self.tank_ctrl = TankController(self.ctx, input_handler, self.modes)
        self.clicks = ClickRouter(input_handler, self.camera_ctrl, self.modes)

        # --- боты ---
        finder = SpawnFinder(self.terrain, blockers=[self.walls.blocks_obb, self.fleet.blocks_obb])
        self.spawner = BotSpawner(self.fleet, finder, camera, self.seed, prefs, settings)
        self.bot_ctrl = BotController(self.ctx)
        self.ram = RamController(self.ctx)
        self.spawner.on_round_finished = self.stats.on_round_finished
        self.fleet.on_destroyed = self.stats.on_enemy_destroyed

    def _load_walls(self, map_data):
        """Стены карты становятся обычными разрушаемыми стенами."""
        load_walls(map_data, self.walls)

    def _place_player(self, player):
        """Игрок стартует в центре карты; если там занято (ручная карта), ищем ближайшее свободное место."""
        finder = SpawnFinder(self.terrain, blockers=[self.walls.blocks_obb])
        spot = finder.find_near(player, 0.0, 0.0, PLAYER_SEARCH_M, heading=0.0)
        if spot is not None:
            player.place_at(spot)

    @property
    def player(self):
        return self.fleet.player

    def update(self, dt, size):
        """Один кадр партии. size — актуальный размер окна (нужен камере)."""
        self.camera_ctrl.update_view(dt, size)

        if self.player.alive:
            self.camera_ctrl.handle_hotkeys()
            self.camera_ctrl.follow(self.player, dt)
            self.modes.handle_hotkeys()
            self.tank_ctrl.handle_hotkeys()

            self.clicks.update()
            self.tank_ctrl.update(dt)
        else:
            self._handle_dead_input()

        self.spawner.update(dt)
        self.bot_ctrl.update(dt)
        self.ram.update(dt)
        self.camera_ctrl.follow(self.player)
        self.combat.update(dt)

    def _handle_dead_input(self):
        """Игрок мёртв: ввод принимается только для Esc (выход в меню)."""
        if not self._death_handled:
            self._death_handled = True
            self.input.detach_ui()                  # бросить ползунок, стрельбу, вращение; слои больше не слушают
            self.modes.set_combat(False)
            self.camera_ctrl.set_free(False)
        self.input.pop_world_clicks()               # накопившиеся клики выбрасываем
        if self.input.was_pressed(Action.CANCEL):
            self._on_exit()