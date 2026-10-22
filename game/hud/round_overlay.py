"""hud/round_overlay.py — правый верхний угол: номер раунда и таймер."""
import math

from engine import get_text, FONT_SIZE_LABEL, FONT_SIZE_TITLE
from ..content import texts
from ..match.rounds.spawner import RoundPhase

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