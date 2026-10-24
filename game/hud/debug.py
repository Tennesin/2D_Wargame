"""game/hud/debug.py — строки отладки (Tab)."""
import pygame
from collections import Counter

from engine import PX_PER_M, VehicleKind
from inputs import Action, key_label
from world import CHUNK_SIZE

class DebugOverlay:
    """Строки отладки (Tab)."""
    TOP = 52
    LINE_H = 20

    def __init__(self, *, clock, ctx, camera_ctrl, tank, world, seed, input_handler, modes, spawner,
                 show_fps=False):
        self.clock = clock
        self.camera = ctx.camera
        self.camera_ctrl = camera_ctrl
        self.tank = tank
        self.world = world
        self.seed = seed
        self.input = input_handler
        self.modes = modes
        self.walls = ctx.walls
        self.fleet = ctx.fleet
        self.effects = ctx.effects
        self.spawner = spawner
        self.visible = False
        self.show_fps = show_fps
        self._font = pygame.font.Font(None, 22)
        self._k = {a: key_label(a) for a in Action}

    def handle_hotkeys(self):
        if self.input.was_pressed(Action.TOGGLE_DEBUG):
            self.visible = not self.visible

    def _lines(self):
        k = self._k
        t = self.tank
        s = t.spec
        owner = self.input.mouse_owner.name if self.input.mouse_owner else "-"
        return [
            f"FPS: {self.clock.get_fps():.0f}",
            f"Zoom: {self.camera.zoom:.2f} (1 m = {PX_PER_M * self.camera.zoom:.0f} px)",
            f"Free camera ({k[Action.TOGGLE_FREE_CAM]}): {'ON' if self.camera_ctrl.free_camera else 'OFF'}",
            f"X: {t.x:.0f}  Y: {t.y:.0f}",
            f"Chunk: {int(t.x // CHUNK_SIZE)}, {int(t.y // CHUNK_SIZE)}",
            f"Grass: {self.world.grass_at(t.x, t.y):.2f}",
            f"Hull: {t.hull_angle:.0f}  Turret: {t.turret_angle:.0f}",
            f"Seed: {self.seed}",
            f"Turret follow ({k[Action.LOCK_TURRET]}): {'ON' if self.modes.turret_follow else 'OFF'}",
            f"Reload: {t.reload_left:.1f}s",
            f"Pos (m): {t.x / PX_PER_M:.1f}, {t.y / PX_PER_M:.1f}",
            f"Walls: {len(self.walls.items)}",
            f"Hull class: {s.HULL_CLASS.name if hasattr(s, 'HULL_CLASS') else '-'}  "
            f"layout: {s.layout.key}  nose: {getattr(s, 'nose', '-')}  "
            f"index: {getattr(s, 'hull_index', 0.0):+.2f}",
            f"Bot hulls: {self._bot_hulls()}",
            f"Hull scale: {s.HULL_SCALE:.2f}  size_k: {s.size_k:.3f}",
            f"Hitbox: {2 * s.COLLISION_HALF_W_PX / PX_PER_M:.2f} x {2 * s.COLLISION_HALF_L_PX / PX_PER_M:.2f} m",
            f"Mode: {self.modes.mode.name}  Mouse owner: {owner}",
            f"Combat ({k[Action.COMBAT]}): {'ON' if self.modes.combat else 'OFF'}",
            f"Speed: {t.speed_kmh:.1f} km/h",
            f"Terrain speed k: {t.terrain_k:.2f}",
            f"Arty: {self._arty_status()}  shells in flight {len(self.effects.artillery_shells)}",
            f"Round {self.spawner.round} {self.spawner.phase.name}  left {self.spawner.time_left:.0f}s  "
            f"bots {len(self.fleet.bots)}  spawned {self.spawner.spawned}",
            f"Fit: {self.spawner.fit_info}",
            f"Threat: " + "  ".join(f"{name} {v:.2f}" for name, v in self.spawner.profile.items()),
            f"Spawn mult: " + "  ".join(f"{name} x{v:.1f}" for name, v in self.spawner.multipliers.items()),
        ]

    def draw(self, screen):
        if self.visible:
            lines = self._lines()
        elif self.show_fps:
            lines = [f"FPS: {self.clock.get_fps():.0f}"]
        else:
            return
        y = self.TOP
        for text in lines:
            shadow = self._font.render(text, True, (0, 0, 0))
            label = self._font.render(text, True, (255, 255, 255))
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += self.LINE_H

    def _arty_status(self):
        """Сколько САУ, сколько из них не стреляют из-за своих и сколько готовы к выстрелу."""
        total = hold = pending = 0
        for b in self.fleet.bots:
            brain = b.brain
            if not hasattr(brain, "pending_zone"):
                continue
            total += 1
            hold += brain.hold_reason == "ally"
            pending += brain.pending_zone is not None
        return f"{total}  hold(ally) {hold}  pending {pending}" if total else "-"

    def _bot_hulls(self):
        """Сколько ботов каждого вида."""
        counts = Counter()
        for b in self.fleet.bots:
            kind = b.brain.arch.kind                       # есть у обоих мозгов
            name = b.tank.spec.HULL_CLASS.name if kind is VehicleKind.MBT else kind.name
            counts[name] += 1
        return "  ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "-"