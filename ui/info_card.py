"""ui/info_card.py — маленькое окно рядом с курсором: заголовок и строки «название ... значение».
О танках и стенах не знает: что показывать, приходит снаружи."""
import pygame

from engine import AlphaLayer, get_text, FONT_SIZE_HEADER, FONT_SIZE_LABEL
from .theme import PANEL_BORDER, TEXT_COLOR, TEXT_DIM, LINE_COLOR, BG_COLOR

CARD_OFFSET = 18           # на сколько px окно смещено от курсора
CARD_PAD = 10              # внутренний отступ
CARD_TITLE_H = 28          # высота строки заголовка
CARD_ROW_H = 22            # высота строки данных
CARD_COL_GAP = 18          # минимальный зазор между названием и значением
CARD_BG = (*BG_COLOR, 225)

class InfoCard:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, mouse_pos, title, rows):
        """title — строка; rows — [(название, значение), ...]."""
        title_s = get_text(title, FONT_SIZE_HEADER, TEXT_COLOR)
        names = [get_text(n, FONT_SIZE_LABEL, TEXT_DIM) for n, _ in rows]
        values = [get_text(v, FONT_SIZE_LABEL, TEXT_COLOR) for _, v in rows]

        rows_w = max((n.get_width() + v.get_width() for n, v in zip(names, values)), default=0)
        w = max(title_s.get_width(), rows_w + CARD_COL_GAP) + 2 * CARD_PAD
        h = 2 * CARD_PAD + CARD_TITLE_H + CARD_ROW_H * len(rows)

        # справа-снизу от курсора; если не влезает, переворачиваем к левой/верхней стороне
        sw, sh = screen.get_size()
        x = mouse_pos[0] + CARD_OFFSET
        y = mouse_pos[1] + CARD_OFFSET
        if x + w > sw:
            x = mouse_pos[0] - CARD_OFFSET - w
        if y + h > sh:
            y = mouse_pos[1] - CARD_OFFSET - h
        rect = pygame.Rect(x, y, w, h).clamp(screen.get_rect())

        # фон: полупрозрачный слой одним blit, текст поверх него прямо на экран
        layer = self._alpha.begin(rect.size)
        pygame.draw.rect(layer, CARD_BG, layer.get_rect(), border_radius=6)
        pygame.draw.rect(layer, PANEL_BORDER, layer.get_rect(), 1, border_radius=6)
        screen.blit(layer, rect.topleft)

        x0, x1 = rect.x + CARD_PAD, rect.right - CARD_PAD
        y = rect.y + CARD_PAD
        screen.blit(title_s, (x0, y))
        line_y = y + CARD_TITLE_H - 4
        pygame.draw.line(screen, LINE_COLOR, (x0, line_y), (x1, line_y), 1)

        y += CARD_TITLE_H
        for name, value in zip(names, values):
            screen.blit(name, (x0, y))
            screen.blit(value, value.get_rect(topright=(x1, y)))
            y += CARD_ROW_H