"""game/hud/status.py — левый нижний угол: сводка по танку, индикаторы боя и подсказки, экран смерти."""
from vehicles import TRACK_SIDES
from engine import get_text, FONT_SIZE_LABEL
from inputs import Action, key_label
from ..content import texts

class HudOverlay:
    """Левый нижний угол: сводка по танку, а над ней индикаторы боевого состояния и подсказки."""

    def __init__(self, hud, tank, modes, camera_ctrl, stats=None):
        self.hud = hud
        self.tank = tank
        self.modes = modes
        self.camera_ctrl = camera_ctrl
        self.stats = stats                   # MatchStats: берём счётчик убийств
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
        if self.stats is not None:
            rows.append((texts.KILLS.format(n=self.stats.kills_total), (170, 176, 186)))

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