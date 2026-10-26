"""game/scenes/play.py — игровая сцена: связывает партию (match) с интерфейсом и отрисовкой.
Логики боя здесь нет: она в Match; рисование в PlayView."""
import random
import pygame

from engine import Team, WORLD
from inputs import InputHandler, AMMO_HOTKEYS, key_label
from ui import SidePanel, ToolBar, AmmoBar
from vehicles import make_vehicle, AMMO_TYPES
from world import Camera, WorldGenerator

from ..content.panels import PanelMode, build_wall_panel, wall_values, WallPanelLink
from ..hud.notifications import Notifier
from ..match.match import Match
from ..match.modes import Mode
from ..view.play_view import PlayView
from .base import Scene

class PlayScene(Scene):
    BACKGROUND = False
    FREE_BACKGROUND = True
    def __init__(self, seed, clock, session, on_result, on_quit):
        """session: настройки танка из конструктора. on_result(stats): показать итоги боя."""
        self.on_quit = on_quit
        self._on_result = on_result
        self.career = session.career
        self._finished = False

        self.seed = seed if seed is not None else random.randrange(1, 1_000_000)
        print(f"Seed мира: {self.seed}")
        self.map_data = session.make_map(self.seed)

        # --- интерфейс, ввод, танк ---
        size = pygame.display.get_surface().get_size()
        WORLD.set_size(self.map_data.width_m, self.map_data.length_m)
        self.camera = Camera(*size)
        self.ui = SidePanel(size, {PanelMode.WALL: build_wall_panel()}, PanelMode.WALL)
        self.toolbar = ToolBar()
        tank = make_vehicle(session.kind, session.spec(), team=Team.PLAYER)
        self.ammo_bar = AmmoBar([(kind, AMMO_TYPES[kind].code, key_label(action))
                                 for kind, action in zip(tank.spec.ammo_kinds, AMMO_HOTKEYS)],
                                tank.select_ammo)
        self.input = InputHandler([self.toolbar, self.ui, self.ammo_bar])
        self.notifier = Notifier(tank)

        # --- партия ---
        self.match = Match(self.map_data, tank, self.camera, self.input, self.notifier,
                           session.prefs, session.settings, on_exit=self._leave)

        # --- связки интерфейса с партией ---
        self.match.modes.on_changed = self._on_mode_changed
        self.toolbar.on_create_wall = self.match.modes.toggle_build
        self.wall_panel = WallPanelLink(self.ui, self.match.wall_editor, self.match.walls)

        # --- рисование ---
        self.view = PlayView(WorldGenerator(self.seed), clock, self.match,
                             self.ui, self.toolbar, self.ammo_bar, self.notifier, session.settings)

    def _on_mode_changed(self, mode, wall):
        """Режим сменился: подстраиваем кнопку тулбара и боковую панель."""
        self.toolbar.set_active(mode == Mode.BUILD)
        if mode == Mode.WALL_EDIT:
            self.ui.show(PanelMode.WALL, wall_values(wall))
        else:
            self.ui.close()

    def _finish_match(self):
        """Партия закончена - итог уходит в накопленную статистику."""
        if self._finished:
            return
        self._finished = True
        stats = self.match.stats
        stats.stop()
        stats.new_records = self.career.add_match(stats)

    def _leave(self):
        """Выход из партии (Esc): сначала итог, потом экран «Итоги боя»."""
        self._finish_match()
        self._on_result(self.match.stats)

    def update(self, dt):
        self.input.process_events()
        if self.input.quit_requested:
            self._finish_match()
            self.on_quit()
            return

        size = pygame.display.get_surface().get_size()   # актуально после изменения размера окна
        if 0 in size:                                    # окно свёрнуто
            return

        self.ui.update(size)
        self.ammo_bar.update(size)
        if self.match.player.alive:
            self.view.handle_hotkeys()

        self.match.update(dt, size)
        if not self.match.player.alive:
            self._finish_match()                         # игрок погиб: итог записываем сразу, не дожидаясь Esc
        self.notifier.update(dt)
        self.wall_panel.update_stats()

    def draw(self, screen):
        self.view.draw(screen)