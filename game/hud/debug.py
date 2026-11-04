"""game/hud/debug.py — строки отладки (Tab)."""
import pygame
from collections import Counter
import math

from engine import PX_PER_M, VehicleKind
from inputs import Action, key_label
from world import CHUNK_SIZE

class DebugOverlay:
    """Строки отладки (Tab)."""
    TOP = 12
    LINE_H = 20
    REFRESH_MS = 200

    def __init__(self, *, clock, ctx, camera_ctrl, tank, world, seed, input_handler, modes, spawner,
                 loot=None, ram=None, show_fps=False):
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
        self.loot = loot
        self.ram = ram
        self.spawner = spawner
        self.visible = False
        self.show_fps = show_fps
        self._font = pygame.font.Font(None, 22)
        self._k = {a: key_label(a) for a in Action}
        self._rendered = []         # [(тень, текст), ...] готовые поверхности
        self._next_refresh = 0      # момент (мс), когда пора пересобрать строки
        self._mode = None           # "full" / "fps" / None: что показывалось в прошлый раз

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
            f"Mouse owner: {owner}",
            f"Combat ({k[Action.COMBAT]}): {'ON' if self.modes.combat else 'OFF'}",
            f"Speed: {t.speed_kmh:.1f} km/h",
            f"Push: {math.hypot(t.push_vx, t.push_vy) / PX_PER_M:.1f} m/s  hull_rate: {t.hull_rate:.0f} deg/s  "
            f"inertia: {s.inertia:.0f} t*m2",
            f"Mods: dmg x{t.mods.dmg_k:.2f} pen x{t.mods.pen_k:.2f} spd x{t.mods.shell_speed_k:.2f} "
            f"rng x{t.mods.shell_range_k:.2f} arm x{t.mods.armor_k:.2f} pwr x{t.mods.power_k:.2f} "
            f"turn x{t.mods.turn_k:.2f} blast x{t.mods.blast_taken_k:.2f}",
            f"Upgrades: {self._upgrades()}",
            f"Terrain speed k: {t.terrain_k:.2f}  kind: {t.terrain_kind.name if t.terrain_kind else '-'}",
            f"Tracks HP: L {t.tracks.health['left'] * 100:.0f}%  R {t.tracks.health['right'] * 100:.0f}%  "
            f"({s.track_mm:.0f} мм, шкала {s.track_max_hp:.0f})",
            f"Arty: {self._arty_status()}  shells in flight {len(self.effects.artillery_shells)}",
            f"Round {self.spawner.round} {self.spawner.phase.name}  left {self.spawner.time_left:.0f}s  "
            f"bots {len(self.fleet.bots)}  spawned {self.spawner.spawned}",
            f"Fit: {self.spawner.fit_info}",
            f"Threat: " + "  ".join(f"{name} {v:.2f}" for name, v in self.spawner.profile.items()),
        ] + self._ram_lines() + self._mult_lines()

    def draw(self, screen):
        if self.visible:
            mode = "full"
            self._draw_contact(screen)
        elif self.show_fps:
            mode = "fps"
        else:
            self._mode = None
            return

        now = pygame.time.get_ticks()
        if mode != self._mode or now >= self._next_refresh:
            lines = self._lines() if mode == "full" else [f"FPS: {self.clock.get_fps():.0f}"]
            self._rendered = [(self._font.render(text, True, (0, 0, 0)),
                               self._font.render(text, True, (255, 255, 255)))
                              for text in lines]
            self._mode = mode
            self._next_refresh = now + self.REFRESH_MS

        y = self.TOP
        for shadow, label in self._rendered:
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += self.LINE_H

    def _mult_lines(self):
        """Множители шансов архетипов, разбитые на две строки (вторая со сдвигом под первой)."""
        items = [f"{name} x{v:.1f}" for name, v in self.spawner.multipliers.items()]
        if not items:
            return ["Spawn mult: -"]
        half = (len(items) + 1) // 2
        lines = ["Spawn mult: " + "  ".join(items[:half])]
        if items[half:]:
            lines.append("                  " + "  ".join(items[half:]))
        return lines

    def _ram_lines(self):
        """Последний удар танков: сближение, импульсы, изменения скорости и вращения, урон."""
        last = None if self.ram is None else self.ram.last
        if last is None:
            return ["Ram: -"]
        return [
            f"Ram {last['age']:.1f}s ago: {last['a']} x {last['b']}  closing {last['closing']:.1f} m/s  "
            f"e {last['e']:.2f}",
            f"   jn {last['jn']:.0f}  jt {last['jt']:.0f}  dv {last['dv_a']:.1f}/{last['dv_b']:.1f} m/s  "
            f"dw {last['dw_a']:.0f}/{last['dw_b']:.0f} deg/s",
            f"   dmg {last['dmg_a']:.0f}/{last['dmg_b']:.0f}  zones {last['zone_a']}/{last['zone_b']}",
        ]

    def _draw_contact(self, screen):
        """Точка и нормаль последнего удара на карте (показывается 1.5 с)."""
        last = None if self.ram is None else self.ram.last
        if last is None or last["age"] > 1.5:
            return
        sx, sy = self.camera.world_to_screen(last["x"], last["y"])
        pygame.draw.circle(screen, (255, 70, 60), (round(sx), round(sy)), 6, 2)
        pygame.draw.line(screen, (255, 220, 60), (sx, sy),
                         (sx + last["nx"] * 40, sy + last["ny"] * 40), 2)

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

    def _upgrades(self):
        """Ячейки улучшений и сколько обломков и останков лежит на карте."""
        if self.loot is None:
            return "-"
        cells = " | ".join(f"{s[0]} {s[1]}" if s else "-" for s in self.loot.slots.slots)
        return f"{cells}   remains {len(self.loot.remains)}  wrecks {len(self.loot.wrecks)}"

    def _bot_hulls(self):
        """Сколько ботов каждого вида."""
        counts = Counter()
        for b in self.fleet.bots:
            kind = b.brain.arch.kind                       # есть у обоих мозгов
            name = b.tank.spec.HULL_CLASS.name if kind is VehicleKind.MBT else kind.name
            counts[name] += 1
        return "  ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "-"