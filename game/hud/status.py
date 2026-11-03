"""game/hud/status.py — левый нижний угол: сводка по танку и экран смерти."""
from engine import get_text
from inputs import Action, key_label
from ..content import texts

class HudOverlay:
    """Сводка по танку и экран смерти. Подсказки и статусы над сводкой убраны: их заменит новая индикация."""

    def __init__(self, hud, tank):
        self.hud = hud
        self.tank = tank
        self._k = {a: key_label(a) for a in Action}

    def draw(self, screen):
        self.hud.draw(screen, self.tank)
        if not self.tank.alive:
            self._draw_death(screen)

    def _draw_death(self, screen):
        cx, cy = screen.get_width() // 2, screen.get_height() // 2
        for text, size, color, dy in ((texts.DEATH_TITLE, 48, (240, 80, 80), -20),
                (texts.DEATH_HINT.format(key=self._k[Action.CANCEL]), 24, (230, 230, 230), 28)):
            shadow = get_text(text, size, (0, 0, 0))
            label = get_text(text, size, color)
            screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy + dy + 2)))
            screen.blit(label, label.get_rect(center=(cx, cy + dy)))