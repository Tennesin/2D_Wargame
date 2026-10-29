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
from ..hud.artillery_warning import ArtilleryWarning
from .world_renderer import Renderer

class PlayView:
    def __init__(self, world, clock, match, ammo_bar, notifier, settings):
        self.match = match
        self.ammo_bar = ammo_bar
        self.notifier = notifier

        ctx = match.ctx
        self.renderer = Renderer(world, ctx, wide=True)
        self.markers = BotMarkers(match.fleet, match.camera)
        self.stun_indicator = StunIndicator(match.fleet, match.camera)
        self.warning = SpawnWarning(match.spawner, match.camera)
        self.artillery_warning = ArtilleryWarning(ctx.effects, match.camera)
        self.debug = DebugOverlay(clock=clock, ctx=ctx, camera_ctrl=match.camera_ctrl, tank=match.player,
                                  world=world, seed=match.seed, input_handler=match.input,
                                  modes=match.modes, spawner=match.spawner,
                                  show_fps=settings.show_fps)
        self.hud = HudOverlay(TankHud(), match.player, match.modes, match.camera_ctrl, match.stats)
        self.round_overlay = RoundOverlay(match.spawner, match.player)
        self.inspector = HoverInspector(ctx, match.input, match.modes)

    def handle_hotkeys(self):
        """Клавиши, которые управляют только показом (сейчас: отладка)."""
        self.debug.handle_hotkeys()

    def draw(self, screen):
        m = self.match
        mouse = m.input.mouse_pos
        alive = m.player.alive

        self.renderer.draw(screen, m.camera, aim=m.combat.aim_info())
        self.markers.draw(screen)
        self.stun_indicator.draw(screen)
        self.artillery_warning.draw(screen)
        if alive:
            self.warning.draw(screen)
        self.debug.draw(screen)
        if alive:
            self.ammo_bar.draw(screen, mouse, m.player.ammo)
        self.hud.draw(screen)
        self.round_overlay.draw(screen)
        self.inspector.draw(screen)
        self.notifier.draw(screen, m.camera)