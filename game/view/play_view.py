"""game/view/play_view.py — всё, что рисуется в партии: мир и поверх него интерфейс.
Порядок слоёв задан здесь одним списком вызовов."""
from ui import TankHud

from ..hud.bot_markers import BotMarkers
from ..hud.debug import DebugOverlay
from ..hud.inspector import HoverInspector
from ..hud.round_overlay import RoundOverlay
from ..hud.spawn_warning import SpawnWarning
from ..hud.status import HudOverlay
from ..hud.stun_indicator import StunIndicator
from .world_renderer import Renderer

class PlayView:
    def __init__(self, world, clock, match, ui, toolbar, ammo_bar, notifier):
        self.match = match
        self.ui = ui
        self.toolbar = toolbar
        self.ammo_bar = ammo_bar
        self.notifier = notifier

        ctx = match.ctx
        self.renderer = Renderer(world, ctx)
        self.renderer.preload(match.camera)
        self.markers = BotMarkers(match.fleet, match.camera)
        self.stun_indicator = StunIndicator(match.fleet, match.camera)
        self.warning = SpawnWarning(match.spawner, match.camera)
        self.debug = DebugOverlay(clock=clock, ctx=ctx, camera_ctrl=match.camera_ctrl, tank=match.player,
                                  world=world, seed=match.seed, input_handler=match.input,
                                  modes=match.modes, spawner=match.spawner)
        self.hud = HudOverlay(TankHud(), match.player, match.modes, match.camera_ctrl, match.fleet)
        self.round_overlay = RoundOverlay(match.spawner, ui, match.player)
        self.inspector = HoverInspector(ctx, match.input, match.modes)

    def handle_hotkeys(self):
        """Клавиши, которые управляют только показом (сейчас: отладка)."""
        self.debug.handle_hotkeys()

    def draw(self, screen):
        m = self.match
        mouse = m.input.mouse_pos
        alive = m.player.alive

        self.renderer.draw(screen, m.camera, m.wall_editor.build_preview(), m.combat.aim_info())
        self.markers.draw(screen)
        self.stun_indicator.draw(screen)
        if alive:
            self.warning.draw(screen)
        self.debug.draw(screen)
        self.ui.draw(screen, mouse)
        if alive:
            self.toolbar.draw(screen, mouse)
            self.ammo_bar.draw(screen, mouse, m.player.ammo)
        self.hud.draw(screen)
        self.round_overlay.draw(screen)      # после ui.draw: панель уже знает свой прямоугольник
        self.inspector.draw(screen)
        self.notifier.draw(screen, m.camera)