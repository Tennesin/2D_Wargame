"""game/match/match.py — одна партия: мир, техника, режимы, контроллеры и порядок кадра.
Ничего не рисует и про интерфейс (панели, кнопки) не знает: всё нужное приходит снаружи.
notifier — приёмник сообщений о бое (его показывает hud, а партия только вызывает его методы)."""
from combat import EffectsSystem, TargetSet
from inputs import Action
from structures import WallManager
from world import TerrainMap, SpawnFinder

from .context import GameContext
from .fleet import Fleet
from .modes import Modes, Mode
from .control.bots import BotController
from .control.camera import CameraController
from .control.clicks import ClickRouter
from .control.hits import CombatController
from .control.player import TankController
from .control.ram import RamController
from .control.wall_editor import WallEditor
from .rounds.spawner import BotSpawner

class Match:
    def __init__(self, seed, player, camera, input_handler, notifier, prefs, on_exit):
        self.seed = seed
        self.camera = camera
        self.input = input_handler
        self._on_exit = on_exit
        self._death_handled = False

        # --- данные ---
        self.terrain = TerrainMap(seed)
        self.terrain.preload()
        self.walls = WallManager()
        self.fleet = Fleet(player)
        self.ctx = GameContext(camera=camera, terrain=self.terrain, walls=self.walls, fleet=self.fleet,
                               effects=EffectsSystem(),
                               targets=TargetSet(self.walls, self.terrain, self.fleet),
                               notifier=notifier)

        # --- контроллеры игрока ---
        self.modes = Modes(input_handler, self.walls)
        self.modes.on_exit = on_exit
        self.camera_ctrl = CameraController(camera, input_handler)
        self.combat = CombatController(self.ctx, self.modes)
        self.tank_ctrl = TankController(self.ctx, input_handler, self.modes)
        self.wall_editor = WallEditor(self.ctx, input_handler, self.modes)
        self.clicks = ClickRouter(input_handler, camera, self.modes, self.camera_ctrl, self.wall_editor)

        # --- боты ---
        finder = SpawnFinder(self.terrain, blockers=[self.walls.blocks_obb, self.fleet.blocks_obb])
        self.spawner = BotSpawner(self.fleet, finder, camera, seed, prefs)
        self.bot_ctrl = BotController(self.ctx)
        self.ram = RamController(self.ctx)

    @property
    def player(self):
        return self.fleet.player

    def update(self, dt, size):
        """Один кадр партии. size — актуальный размер окна (нужен камере)."""
        self.camera_ctrl.update_view(dt, size)

        if self.player.alive:
            self.camera_ctrl.handle_hotkeys()
            self.camera_ctrl.follow(self.player, dt)
            self.wall_editor.handle_hotkeys()
            self.modes.handle_hotkeys()
            self.tank_ctrl.handle_hotkeys()

            self.clicks.update()
            self.wall_editor.update_rotation()
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
            self.modes.set_mode(Mode.DRIVE)         # через on_changed закроет панель и снимет выбор стены
            self.modes.set_combat(False)
            self.camera_ctrl.set_free(False)
        self.input.pop_world_clicks()               # накопившиеся клики выбрасываем
        if self.input.was_pressed(Action.CANCEL):
            self._on_exit()