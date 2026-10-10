"""game/scenes/play.py — игровая сцена: сборка частей и покадровый порядок вызовов.
Логики здесь нет: каждая зона живёт в своём классе."""
import random

import pygame

from world import Camera, WorldGenerator, TerrainMap, SpawnFinder
from vehicles import Tank
from structures import WallManager
from inputs import InputHandler
from ui import ConstructorUI, ToolBar, TankHud
from ..panels import PanelMode, build_wall_panel
from ..modes import Modes
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
from ..bot_markers import BotMarkers
from ..notifications import Notifier
from .base import Scene

DEBUG_PRINT_SPECS = False     # печатать характеристики танка в консоль при запуске

class PlayScene(Scene):
    def __init__(self, seed, clock, session, on_menu, on_quit):
        """session: настройки танка из конструктора."""
        self.on_quit = on_quit
        size = pygame.display.get_surface().get_size()

        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        print(f"Seed мира: {self.seed}")

        # --- данные ---
        world = WorldGenerator(self.seed)
        terrain = TerrainMap(self.seed)
        walls = WallManager()
        self.camera = Camera(*size)

        # --- интерфейс, ввод, танк ---
        self.ui = ConstructorUI(size, {PanelMode.WALL: build_wall_panel()}, PanelMode.WALL,
                                has_toggle=False)
        self.toolbar = ToolBar()
        self.input = InputHandler([self.toolbar, self.ui])
        tank = Tank(0.0, 0.0, spec=session.tank_spec(), team="player")
        fleet = Fleet(tank)
        self.fleet = fleet
        self.notifier = Notifier(tank)
        if DEBUG_PRINT_SPECS:
            tank.spec.print_specs()

        # --- контроллеры ---
        modes = Modes(self.input, walls, self.toolbar, self.ui)
        modes.on_exit = on_menu
        self.camera_ctrl = CameraController(self.camera, self.input)
        self.combat = CombatController(tank, walls, terrain, modes, fleet, self.notifier)
        self.tank_ctrl = TankController(tank, self.input, self.camera, modes, walls, terrain,
                                        self.combat.effects, fleet)
        self.wall_editor = WallEditor(self.input, self.camera, modes, walls, fleet, terrain, self.ui)
        self.clicks = ClickRouter(self.input, self.camera, modes, self.camera_ctrl, self.wall_editor)

        # --- боты ---
        finder = SpawnFinder(terrain, blockers=[walls.blocks_obb, fleet.blocks_obb])
        self.spawner = BotSpawner(fleet, finder, self.camera, self.seed)
        self.bot_ctrl = BotController(fleet, walls, terrain, self.combat.effects, self.combat.targets)

        # --- рисование ---
        self.renderer = Renderer(world, terrain, fleet, walls, self.combat.effects)
        self.markers = BotMarkers(fleet, self.camera)
        self.debug = DebugOverlay(clock=clock, camera=self.camera, camera_ctrl=self.camera_ctrl,
                                  tank=tank, world=world, seed=self.seed, input_handler=self.input,
                                  modes=modes, walls=walls, fleet=fleet, spawner=self.spawner)
        self.hud = HudOverlay(TankHud(), tank, modes, self.camera_ctrl, self.combat)
        self.modes = modes

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

        self.debug.handle_hotkeys()
        self.camera_ctrl.handle_hotkeys()
        self.wall_editor.handle_hotkeys()
        self.modes.handle_hotkeys()

        self.clicks.update()
        self.wall_editor.update_rotation()
        if self.fleet.player.alive:
            self.tank_ctrl.update(dt)
        self.spawner.update(dt)
        self.bot_ctrl.update(dt)
        self.camera_ctrl.follow(self.fleet.player)
        self.combat.update(dt)
        self.notifier.update(dt)
        self.wall_editor.update_stats()

    def draw(self, screen):
        self.renderer.draw(screen, self.camera, self.wall_editor.build_preview(), self.combat.aim_info())
        self.markers.draw(screen)
        self.debug.draw(screen)
        self.ui.draw(screen, self.input.mouse_pos)
        self.toolbar.draw(screen, self.input.mouse_pos)
        self.hud.draw(screen)
        self.notifier.draw(screen, self.camera)