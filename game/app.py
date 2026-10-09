"""game/app.py — окно, главный цикл и сборка частей. Логики здесь нет: каждая зона живёт в своём классе."""
import random

import pygame

from world import Camera, WorldGenerator, TerrainMap
from vehicles import Tank, TankSpec
from structures import WallManager
from inputs import InputHandler
from ui import ConstructorUI, ToolBar, TankHud
from .panels import PanelMode, build_panels
from .modes import Modes
from .camera_control import CameraController
from .combat_control import CombatController
from .tank_control import TankController
from .wall_editor import WallEditor
from .clicks import ClickRouter
from .overlays import DebugOverlay, HudOverlay
from .renderer import Renderer

DEBUG_PRINT_SPECS = False     # печатать характеристики танка в консоль при запуске

class Game:
    MAX_DT = 0.05   # защита от «телепорта» при подвисании окна

    def __init__(self, seed=None):
        pygame.init()
        screen = pygame.display.set_mode((1000, 700), pygame.RESIZABLE)
        pygame.display.set_caption("Top-Down Танк (бесконечный мир)")
        self.clock = pygame.time.Clock()

        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        print(f"Seed мира: {self.seed}")

        # --- данные ---
        world = WorldGenerator(self.seed)
        terrain = TerrainMap(self.seed)
        walls = WallManager()
        self.camera = Camera(*screen.get_size())

        # --- интерфейс, ввод, танк ---
        self.ui = ConstructorUI(screen.get_size(), build_panels(), PanelMode.TANK)
        self.toolbar = ToolBar()
        self.input = InputHandler([self.toolbar, self.ui])
        tank = Tank(0.0, 0.0, spec=TankSpec.from_values(self.ui.get_values(PanelMode.TANK)))
        if DEBUG_PRINT_SPECS:
            tank.spec.print_specs()

        # --- контроллеры ---
        modes = Modes(self.input, walls, self.toolbar, self.ui)
        self.camera_ctrl = CameraController(self.camera, self.input)
        self.combat = CombatController(tank, walls, terrain, modes)
        self.tank_ctrl = TankController(tank, self.input, self.camera, modes, walls, terrain,
                                        self.combat.effects, self.ui)
        self.wall_editor = WallEditor(self.input, self.camera, modes, walls, tank, terrain, self.ui)
        self.clicks = ClickRouter(self.input, self.camera, modes, self.camera_ctrl, self.wall_editor)

        # --- рисование ---
        self.renderer = Renderer(world, terrain, tank, walls, self.combat.effects)
        self.debug = DebugOverlay(clock=self.clock, camera=self.camera, camera_ctrl=self.camera_ctrl,
                                  tank=tank, world=world, seed=self.seed, input_handler=self.input,
                                  modes=modes, walls=walls)
        self.hud = HudOverlay(TankHud(), tank, modes, self.camera_ctrl)
        self.modes = modes

    def run(self):
        while not self.input.quit_requested:
            dt = min(self.clock.tick(60) / 1000.0, self.MAX_DT)
            self.input.process_events()

            screen = pygame.display.get_surface()      # актуально после изменения размера окна
            size = screen.get_size()
            if 0 in size:
                continue

            self._update(dt, size)
            self._draw(screen)
            pygame.display.flip()

    def _update(self, dt, size):
        self.camera_ctrl.update_view(dt, size)
        self.ui.update(size)

        self.debug.handle_hotkeys()
        self.camera_ctrl.handle_hotkeys()
        self.wall_editor.handle_hotkeys()
        self.modes.handle_hotkeys()

        self.clicks.update()
        self.wall_editor.update_rotation()
        self.tank_ctrl.update(dt)
        self.camera_ctrl.follow(self.tank_ctrl.tank)
        self.combat.update(dt)
        self.wall_editor.update_stats()

    def _draw(self, screen):
        self.renderer.draw(screen, self.camera, self.wall_editor.build_preview(), self.combat.aim_info())
        self.debug.draw(screen)
        self.ui.draw(screen, self.input.mouse_pos)
        self.toolbar.draw(screen, self.input.mouse_pos)
        self.hud.draw(screen)