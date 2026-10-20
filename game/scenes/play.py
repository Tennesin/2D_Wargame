"""game/scenes/play.py — игровая сцена: сборка частей и покадровый порядок вызовов.
Логики здесь нет: каждая зона живёт в своём классе."""
import random

import pygame

from world import Camera, WorldGenerator, TerrainMap, SpawnFinder
from vehicles import make_vehicle, AMMO_TYPES, AMMO_ORDER
from structures import WallManager
from inputs import InputHandler, Action, AMMO_HOTKEYS, key_label
from ui import SidePanel, ToolBar, TankHud, AmmoBar
from ..panels import PanelMode, build_wall_panel
from ..modes import Modes, Mode
from ..camera_control import CameraController
from ..combat_control import CombatController
from ..tank_control import TankController
from ..wall_editor import WallEditor
from ..clicks import ClickRouter
from ..overlays import DebugOverlay, HudOverlay
from ..renderer import Renderer
from ..fleet import Fleet
from ..spawner import BotSpawner
from ..bot_control import BotController
from ..ram_control import RamController
from ..bot_markers import BotMarkers
from ..inspector import HoverInspector
from ..notifications import Notifier
from .base import Scene
from combat import EffectsSystem, TargetSet
from engine import Team
from ..context import GameContext

class PlayScene(Scene):
    def __init__(self, seed, clock, session, on_menu, on_quit):
        """session: настройки танка из конструктора."""
        self.on_quit = on_quit
        self.on_menu = on_menu
        self._death_handled = False
        size = pygame.display.get_surface().get_size()

        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        print(f"Seed мира: {self.seed}")

        # --- данные ---
        world = WorldGenerator(self.seed)
        terrain = TerrainMap(self.seed)
        walls = WallManager()
        self.camera = Camera(*size)

        # --- интерфейс, ввод, танк ---
        self.ui = SidePanel(size, {PanelMode.WALL: build_wall_panel()}, PanelMode.WALL)
        self.toolbar = ToolBar()
        tank = make_vehicle(session.kind, session.spec(), team=Team.PLAYER)
        self.ammo_bar = AmmoBar([(kind, AMMO_TYPES[kind].code, key_label(action))
                                 for kind, action in zip(AMMO_ORDER, AMMO_HOTKEYS)],
                                tank.select_ammo)
        self.input = InputHandler([self.toolbar, self.ui, self.ammo_bar])
        fleet = Fleet(tank)
        self.fleet = fleet
        self.notifier = Notifier(tank)

        # --- общий контекст партии ---
        ctx = GameContext(camera=self.camera, terrain=terrain, walls=walls, fleet=fleet,
                          effects=EffectsSystem(), targets=TargetSet(walls, terrain, fleet),
                          notifier=self.notifier)

        # --- контроллеры ---
        modes = Modes(self.input, walls, self.toolbar, self.ui)
        modes.on_exit = on_menu
        self.camera_ctrl = CameraController(self.camera, self.input)
        self.combat = CombatController(ctx, modes)
        self.tank_ctrl = TankController(ctx, self.input, modes)
        self.wall_editor = WallEditor(ctx, self.input, modes, self.ui)
        self.clicks = ClickRouter(self.input, self.camera, modes, self.camera_ctrl, self.wall_editor)

        # --- боты ---
        finder = SpawnFinder(terrain, blockers=[walls.blocks_obb, fleet.blocks_obb])
        self.spawner = BotSpawner(fleet, finder, self.camera, self.seed, session.prefs)
        self.bot_ctrl = BotController(ctx)
        self.ram = RamController(ctx)

        # --- рисование ---
        self.renderer = Renderer(world, ctx)
        self.markers = BotMarkers(fleet, self.camera)
        self.debug = DebugOverlay(clock=clock, ctx=ctx, camera_ctrl=self.camera_ctrl, tank=tank,
                                  world=world, seed=self.seed, input_handler=self.input,
                                  modes=modes, spawner=self.spawner)
        self.hud = HudOverlay(TankHud(), tank, modes, self.camera_ctrl, fleet)
        self.modes = modes
        self.inspector = HoverInspector(ctx, self.input, modes)

    def update(self, dt):
        self.input.process_events()
        if self.input.quit_requested:
            self.on_quit()
            return

        size = pygame.display.get_surface().get_size()   # актуально после изменения размера окна
        if 0 in size:                                    # окно свёрнуто
            return

        self.camera_ctrl.update_view(dt, size)
        self.ui.update(size)
        self.ammo_bar.update(size)

        if self.fleet.player.alive:
            self.debug.handle_hotkeys()
            self.camera_ctrl.follow(self.fleet.player, dt)
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
        self.camera_ctrl.follow(self.fleet.player)
        self.combat.update(dt)
        self.notifier.update(dt)
        self.wall_editor.update_stats()

    def _handle_dead_input(self):
        """Игрок мёртв: ввод принимается только для Esc (выход в меню)."""
        if not self._death_handled:
            self._death_handled = True
            self.input.release_mouse()              # бросить ползунок, стрельбу, вращение
            self.input.ui_layers.clear()            # тулбар и панель больше не получают события
            self.modes.set_mode(Mode.DRIVE)         # закрывает панель, снимает выбор стены
            self.modes.set_combat(False)
            self.camera_ctrl.set_free(False)
        self.input.pop_world_clicks()               # накопившиеся клики выбрасываем
        if self.input.was_pressed(Action.CANCEL):
            self.on_menu()

    def draw(self, screen):
        self.renderer.draw(screen, self.camera, self.wall_editor.build_preview(), self.combat.aim_info())
        self.markers.draw(screen)
        self.debug.draw(screen)
        self.ui.draw(screen, self.input.mouse_pos)
        if self.fleet.player.alive:
            self.toolbar.draw(screen, self.input.mouse_pos)
            self.ammo_bar.draw(screen, self.input.mouse_pos, self.fleet.player.ammo)
        self.hud.draw(screen)
        self.inspector.draw(screen)
        self.notifier.draw(screen, self.camera)