"""hud/debug.py — строки отладки (Tab)."""
import pygame
from collections import Counter

from engine import PX_PER_M
from inputs import Action, key_label
from world import CHUNK_SIZE

class DebugOverlay:
    """Строки отладки (Tab)."""
    TOP = 52
    LINE_H = 20

    def __init__(self, *, clock, ctx, camera_ctrl, tank, world, seed, input_handler, modes, spawner):
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
        self.spawner = spawner
        self.visible = False
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
            f"Round {self.spawner.round} {self.spawner.phase.name}  left {self.spawner.time_left:.0f}s  "
            f"bots {len(self.fleet.bots)}  spawned {self.spawner.spawned}",
            f"Fit: {self.spawner.fit_info}",
            f"spawned {self.spawner.spawned}",
            f"Threat: " + "  ".join(f"{name} {v:.2f}" for name, v in self.spawner.profile.items()),
            f"Spawn mult: " + "  ".join(f"{name} x{v:.1f}" for name, v in self.spawner.multipliers.items()),
        ]

    def draw(self, screen):
        if not self.visible:
            return
        y = self.TOP
        for text in self._lines():
            shadow = self._font.render(text, True, (0, 0, 0))
            label = self._font.render(text, True, (255, 255, 255))
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += self.LINE_H

    def _bot_hulls(self):
        """Сколько ботов каждого класса корпуса (ПТ-САУ считаются отдельно)."""
        classes = (getattr(b.tank.spec, "HULL_CLASS", None) for b in self.fleet.bots)
        counts = Counter(c.name if c else "TD" for c in classes)
        return "  ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "-"