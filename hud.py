"""hud.py — компактная сводка по танку в левом нижнем углу."""
import pygame

from common import clamp
from ui import get_font, FONT_SIZE_LABEL
from common import clamp, fmt_num

MARGIN = 10          # отступ от краёв окна
WIDTH = 190
PAD = 8
ROW_H = 20
BAR_H = 8
BAR_GAP = 6
HEIGHT = PAD * 2 + (ROW_H + BAR_H + BAR_GAP) * 2 + ROW_H * 3   # два блока с полоской + три строки

BG = (0, 0, 0, 150)
BORDER = (70, 76, 86)
C_TEXT = (230, 230, 230)
C_DIM = (150, 156, 166)
C_BAR_BG = (45, 49, 56)
C_HP_OK = (90, 200, 90)
C_HP_MID = (230, 200, 70)
C_HP_LOW = (230, 80, 70)
C_LOADING = (230, 170, 60)
C_READY = (90, 200, 90)

class TankHud:
    def __init__(self):
        self._bg = None

    def draw(self, screen, tank):
        """Рисует сводку и возвращает y её верхнего края (чтобы над ней можно было поставить подсказки)."""
        rect = pygame.Rect(MARGIN, screen.get_height() - MARGIN - HEIGHT, WIDTH, HEIGHT)
        if self._bg is None:
            self._bg = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(self._bg, BG, self._bg.get_rect(), border_radius=6)
            pygame.draw.rect(self._bg, BORDER, self._bg.get_rect(), 1, border_radius=6)
        screen.blit(self._bg, rect.topleft)

        font = get_font(FONT_SIZE_LABEL)
        spec = tank.spec
        x0, x1 = rect.x + PAD, rect.right - PAD
        y = rect.y + PAD

        # 1. Здоровье
        hp_frac = clamp(tank.hp / tank.max_hp, 0.0, 1.0) if tank.max_hp > 0 else 0.0
        hp_color = C_HP_OK if hp_frac > 0.6 else C_HP_MID if hp_frac > 0.3 else C_HP_LOW
        y = self._row(screen, font, x0, x1, y, "Здоровье", f"{fmt_num(tank.hp)} / {fmt_num(tank.max_hp)}")
        y = self._bar(screen, x0, x1, y, hp_frac, hp_color)

        # 2. Урон и пробитие
        y = self._row(screen, font, x0, x1, y, "Урон", fmt_num(spec.damage))
        y = self._row(screen, font, x0, x1, y, "Пробитие", f"{spec.penetration:.0f} мм")

        # 3. Перезарядка: полоска заполняется после выстрела
        if tank.reload_left <= 0.0 or spec.reload <= 0.0:
            reload_frac, reload_text, reload_color = 1.0, "готово", C_READY
        else:
            reload_frac = clamp(1.0 - tank.reload_left / spec.reload, 0.0, 1.0)
            reload_text, reload_color = f"{tank.reload_left:.1f} с", C_LOADING
        y = self._row(screen, font, x0, x1, y, "Перезарядка", reload_text)
        y = self._bar(screen, x0, x1, y, reload_frac, reload_color)

        # 4. Скорость
        speed = f"{abs(tank.speed_kmh):.0f} км/ч"
        if tank.speed_kmh < -0.5:
            speed += " (назад)"
        self._row(screen, font, x0, x1, y, "Скорость", speed)

        return rect.top

    @staticmethod
    def _row(screen, font, x0, x1, y, name, value):
        screen.blit(font.render(name, True, C_DIM), (x0, y))
        val = font.render(value, True, C_TEXT)
        screen.blit(val, val.get_rect(topright=(x1, y)))
        return y + ROW_H

    @staticmethod
    def _bar(screen, x0, x1, y, frac, color):
        bg = pygame.Rect(x0, y, x1 - x0, BAR_H)
        pygame.draw.rect(screen, C_BAR_BG, bg, border_radius=3)
        if frac > 0.0:
            fill = pygame.Rect(x0, y, max(2, int(bg.width * frac)), BAR_H)
            pygame.draw.rect(screen, color, fill, border_radius=3)
        return y + BAR_H + BAR_GAP