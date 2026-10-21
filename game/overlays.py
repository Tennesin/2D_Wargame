"""game/overlays.py — текст поверх игры: отладочные строки и подсказки над HUD."""
import math
import pygame
from collections import Counter

from vehicles import TRACK_SIDES
from engine import PX_PER_M, get_text, FONT_SIZE_LABEL, FONT_SIZE_TITLE
from inputs import Action, key_label
from world import CHUNK_SIZE
from . import texts
from .spawner import RoundPhase

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

class HudOverlay:
    """Левый нижний угол: сводка по танку, а над ней индикаторы боевого состояния и подсказки."""

    def __init__(self, hud, tank, modes, camera_ctrl, fleet=None):
        self.hud = hud
        self.tank = tank
        self.modes = modes
        self.camera_ctrl = camera_ctrl
        self.fleet = fleet                   # Fleet: берём счётчик убийств
        self._k = {a: key_label(a) for a in Action}

    def draw(self, screen):
        y = self.hud.draw(screen, self.tank) - 6
        if not self.tank.alive:
            self._draw_death(screen)
            return

        k = self._k
        rows = []
        if self.modes.combat:
            rows.append((texts.HINT_COMBAT, (240, 80, 80)))
        else:
            rows.append((texts.HINT_IDLE.format(combat=k[Action.COMBAT], camera=k[Action.TOGGLE_FREE_CAM],
                                                debug=k[Action.TOGGLE_DEBUG]), (170, 176, 186)))
        rows.append((texts.HINT_AMMO.format(a=k[Action.AMMO_1], b=k[Action.AMMO_2], c=k[Action.AMMO_3]),
                     (170, 176, 186)))
        if self.camera_ctrl.free_camera:
            rows.append((texts.HINT_FREE_CAM.format(key=k[Action.TOGGLE_FREE_CAM]), (110, 190, 240)))
        if self.tank.terrain_k < 0.99:
            rows.append((texts.HINT_VISCOUS.format(k=self.tank.terrain_k), (200, 170, 120)))
        tracks = self.tank.tracks
        if tracks.repair_side is not None:
            rows.append((texts.HINT_TRACK_REPAIR.format(side=texts.TRACK_RU[tracks.repair_side],
                                                        t=tracks.repair_left), (240, 210, 70)))
        elif tracks.broken:
            sides = ", ".join(texts.TRACK_RU[s] for s in TRACK_SIDES if tracks.is_broken(s))
            rows.append((texts.HINT_TRACK_BROKEN.format(sides=sides, key=k[Action.REPAIR]), (240, 80, 80)))
        if self.tank.stunned:
            rows.append((texts.HINT_STUNNED.format(t=self.tank.stun_left), (240, 210, 70)))
        if not self.modes.turret_follow:
            rows.append((texts.HINT_TURRET_LOCKED.format(key=k[Action.LOCK_TURRET]), (240, 210, 70)))
        if self.fleet is not None:
            rows.append((texts.KILLS.format(n=self.fleet.kills), (170, 176, 186)))

        for text, color in reversed(rows):
            shadow = get_text(text, FONT_SIZE_LABEL, (0, 0, 0))
            label = get_text(text, FONT_SIZE_LABEL, color)
            y -= label.get_height() + 2
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))

    def _draw_death(self, screen):
        cx, cy = screen.get_width() // 2, screen.get_height() // 2
        for text, size, color, dy in ((texts.DEATH_TITLE, 48, (240, 80, 80), -20),
                (texts.DEATH_HINT.format(key=self._k[Action.CANCEL]), 24, (230, 230, 230), 28)):
            shadow = get_text(text, size, (0, 0, 0))
            label = get_text(text, size, color)
            screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy + dy + 2)))
            screen.blit(label, label.get_rect(center=(cx, cy + dy)))

class RoundOverlay:
    """Правый верхний угол: номер раунда и таймер. Если справа открыта панель, сдвигается влево от неё."""
    TOP = 12
    GAP = 12
    LINE_GAP = 4

    def __init__(self, spawner, ui, player):
        self.spawner = spawner
        self.ui = ui
        self.player = player

    def draw(self, screen):
        sp = self.spawner
        if sp.round == 0 or not self.player.alive:
            return

        rows = [(texts.ROUND_TITLE.format(n=sp.round), FONT_SIZE_TITLE, (235, 235, 235))]
        if sp.phase is RoundPhase.COUNTDOWN:
            if sp.time_left > 0.0:
                rows.append((texts.ROUND_STARTS_IN.format(t=math.ceil(sp.time_left)),
                             FONT_SIZE_LABEL, (240, 210, 70)))
            else:
                rows.append((texts.ROUND_WAITING, FONT_SIZE_LABEL, (240, 210, 70)))
        else:
            rows.append((texts.ROUND_TIME_LEFT.format(t=math.ceil(sp.time_left)),
                         FONT_SIZE_LABEL, (170, 176, 186)))
            rows.append((texts.ROUND_ENEMIES.format(alive=sp.group_alive, total=sp.group_total),
                         FONT_SIZE_LABEL, (170, 176, 186)))

        right = (self.ui.panel_rect.left if self.ui.is_open else screen.get_width()) - self.GAP
        y = self.TOP
        for text, size, color in rows:
            shadow = get_text(text, size, (0, 0, 0))
            label = get_text(text, size, color)
            screen.blit(shadow, shadow.get_rect(topright=(right + 1, y + 1)))
            screen.blit(label, label.get_rect(topright=(right, y)))
            y += label.get_height() + self.LINE_GAP