"""ui/upgrade_bar.py — панель улучшений у правого края: три ячейки, треугольник-разворот, карточка предложения.
О танках и улучшениях не знает: данные приходят снаружи готовыми (CellView, OfferView)."""
from typing import NamedTuple
import pygame

from engine import (get_text, get_font, wrap_text, shade_color, lerp_color,
                    FONT_SIZE_HEADER, FONT_SIZE_LABEL)
from .plate import draw_plate
from .theme import (ACTIVE_BUTTON_COLORS, BUTTON_COLORS, PANEL_BORDER, SLIDER_BG_COLOR,
                    TEXT_COLOR, TEXT_DIM)
from .widgets import Button

SLOTS = 3
CELL = 52                  # сторона ячейки
GAP = 8                    # зазор между ячейками и до соседних элементов
EDGE_MARGIN = 10           # от правого края окна до треугольника
BOTTOM_MARGIN = 10         # от нижнего края окна до нижней ячейки
TRI_W, TRI_H = 18, 44
ROW_W = 340                # ширина раскрытой строки
CARD_W = 300
CARD_PAD = 10
CARD_TITLE_H = 24
CARD_LINE_H = 20
BTN_H = 34

PIP = 8                    # метка уровня
PIP_GAP = 4
PIP_ON = (240, 210, 70)
PIP_OFF = (30, 33, 38)
SELECT = (255, 220, 80)    # рамка ячеек, когда нужно выбрать замену
LIGHT_EDGE = (200, 205, 212)

class CellView(NamedTuple):
    title: str
    level: int
    max_level: int
    color: tuple
    effect: str            # текст эффекта текущего уровня

class OfferView(NamedTuple):
    title: str
    color: tuple
    info: str              # что изменится, если взять
    replace: bool          # все ячейки заняты: игрок выбирает, какую заменить
    take_label: str
    decline_label: str

def _geometry(size):
    """(треугольник, [прямоугольники ячеек]) для окна size. Колонка прижата к правому нижнему углу."""
    w, h = size
    col_h = SLOTS * CELL + (SLOTS - 1) * GAP
    top = h - BOTTOM_MARGIN - col_h
    tri = pygame.Rect(w - EDGE_MARGIN - TRI_W, top + col_h // 2 - TRI_H // 2, TRI_W, TRI_H)
    x = tri.left - GAP - CELL
    return tri, [pygame.Rect(x, top + i * (CELL + GAP), CELL, CELL) for i in range(SLOTS)]

def right_zone(size):
    """Область, которую панель занимает всегда (ячейки и треугольник): от неё уходят указатели у края."""
    _, cells = _geometry(size)
    left, top = cells[0].left, cells[0].top
    return pygame.Rect(left, top, size[0] - left, cells[-1].bottom - top)

class UpgradeBar:
    def __init__(self):
        self.on_take = None            # функция(): взять (если ячейка не нужна)
        self.on_decline = None         # функция(): отказаться
        self.on_replace = None         # функция(номер ячейки): заменить именно её
        self.expanded = False          # раскрыты ли строки (треугольник)

        self._cells = [None] * SLOTS
        self._offer = None
        self._tri = pygame.Rect(0, 0, 1, 1)
        self._cell_rects = []
        self._row_rects = []
        self._card = pygame.Rect(0, 0, 0, 0)
        self._info_lines = []
        self.take_button = Button((0, 0, 10, BTN_H), "")
        self.decline_button = Button((0, 0, 10, BTN_H), "")
        self._size = None
        self.update(pygame.display.get_surface().get_size())

    # ---------- состояние ----------
    @property
    def _rows_shown(self):
        """Строки видны, если их раскрыли или идёт выбор ячейки для замены."""
        return self.expanded or (self._offer is not None and self._offer.replace)

    def update(self, size):
        """Раскладка пересчитывается только при смене размера окна."""
        if size != self._size:
            self._size = size
            self._relayout()

    def set_state(self, cells, offer):
        """cells: список из SLOTS элементов (CellView или None); offer: OfferView или None. Каждый кадр."""
        changed = offer != self._offer
        self._cells = list(cells)
        self._offer = offer
        if changed:
            self._relayout()

    def _relayout(self):
        self._tri, self._cell_rects = _geometry(self._size)
        self._row_rects = [pygame.Rect(c.left - GAP - ROW_W, c.y, ROW_W, CELL) for c in self._cell_rects]
        offer = self._offer
        if offer is None:
            self._info_lines = []
            return
        self._info_lines = wrap_text(get_font(FONT_SIZE_LABEL), offer.info, CARD_W - 2 * CARD_PAD - 6)
        height = (CARD_PAD + CARD_TITLE_H + CARD_LINE_H * len(self._info_lines)
                  + 8 + BTN_H + CARD_PAD)
        first = self._cell_rects[0]
        self._card = pygame.Rect(first.right - CARD_W, first.top - GAP - height, CARD_W, height)

        inner_x = self._card.x + CARD_PAD
        inner_w = CARD_W - 2 * CARD_PAD
        y = self._card.bottom - CARD_PAD - BTN_H
        self.take_button.label = offer.take_label
        self.decline_button.label = offer.decline_label
        if offer.replace:
            self.take_button.enabled = False
            self.decline_button.rect = pygame.Rect(inner_x, y, inner_w, BTN_H)
        else:
            self.take_button.enabled = True
            half = (inner_w - GAP) // 2
            self.take_button.rect = pygame.Rect(inner_x, y, half, BTN_H)
            self.decline_button.rect = pygame.Rect(inner_x + half + GAP, y, half, BTN_H)

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        if self._tri.collidepoint(pos) or any(r.collidepoint(pos) for r in self._cell_rects):
            return True
        if self._rows_shown and any(r.collidepoint(pos) for r in self._row_rects):
            return True
        return self._offer is not None and self._card.collidepoint(pos)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        if event.type != pygame.MOUSEBUTTONDOWN or not self.covers(event.pos):
            return False
        if event.button == 1:
            self._click(event.pos)
        return True                      # любые клики по панели поглощаем: выстрела не будет

    def _click(self, pos):
        if self._tri.collidepoint(pos):
            self.expanded = not self.expanded
            return
        offer = self._offer
        if offer is None:
            return
        if offer.replace:
            for i, rect in enumerate(self._cell_rects):
                if rect.collidepoint(pos):
                    if self.on_replace is not None:
                        self.on_replace(i)
                    return
        if self.take_button.collidepoint(pos):
            if self.on_take is not None:
                self.on_take()
        elif self.decline_button.collidepoint(pos):
            if self.on_decline is not None:
                self.on_decline()

    # ---------- рисование ----------
    def draw(self, screen, mouse_pos):
        offer = self._offer
        replace = offer is not None and offer.replace
        if self._rows_shown:
            for rect, cell in zip(self._row_rects, self._cells):
                self._draw_row(screen, rect, cell)
        for i, (rect, cell) in enumerate(zip(self._cell_rects, self._cells)):
            self._draw_cell(screen, rect, cell, i, replace and rect.collidepoint(mouse_pos), replace)
        self._draw_triangle(screen, mouse_pos)
        if offer is not None:
            self._draw_card(screen, mouse_pos, offer)

    @staticmethod
    def _draw_row(screen, rect, cell):
        draw_plate(screen, rect, alpha=205, radius=6)
        if cell is None:
            dash = get_text("-", FONT_SIZE_HEADER, TEXT_DIM)
            screen.blit(dash, dash.get_rect(midleft=(rect.x + 12, rect.centery)))
            return
        screen.blit(get_text(cell.title, FONT_SIZE_HEADER, TEXT_COLOR), (rect.x + 12, rect.y + 6))
        level = get_text(f"ур. {cell.level}/{cell.max_level}", FONT_SIZE_LABEL, TEXT_DIM)
        screen.blit(level, level.get_rect(topright=(rect.right - 12, rect.y + 8)))
        screen.blit(get_text(cell.effect, FONT_SIZE_LABEL, TEXT_DIM), (rect.x + 12, rect.y + 28))

    @staticmethod
    def _draw_cell(screen, rect, cell, index, hover, replace):
        if cell is None:
            pygame.draw.rect(screen, SLIDER_BG_COLOR, rect, border_radius=6)
            pygame.draw.rect(screen, PANEL_BORDER, rect, 1, border_radius=6)
            num = get_text(str(index + 1), FONT_SIZE_LABEL, TEXT_DIM)
            screen.blit(num, num.get_rect(center=rect.center))
        else:
            pygame.draw.rect(screen, shade_color(cell.color, 0.65 if hover else 0.45), rect, border_radius=6)
            pygame.draw.rect(screen, cell.color, rect, 2, border_radius=6)
            cx, cy, d = rect.centerx, rect.y + 22, 11
            diamond = [(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)]
            pygame.draw.polygon(screen, cell.color, diamond)
            pygame.draw.polygon(screen, LIGHT_EDGE, diamond, 1)
            total = cell.max_level * PIP + (cell.max_level - 1) * PIP_GAP
            x = rect.centerx - total // 2
            for i in range(cell.max_level):
                color = PIP_ON if i < cell.level else PIP_OFF
                pygame.draw.rect(screen, color, (x + i * (PIP + PIP_GAP), rect.bottom - 13, PIP, PIP), border_radius=2)
        if replace:
            pygame.draw.rect(screen, SELECT, rect, 3, border_radius=6)

    def _draw_triangle(self, screen, mouse_pos):
        bg = BUTTON_COLORS["hover"] if self._tri.collidepoint(mouse_pos) else BUTTON_COLORS["normal"]
        pygame.draw.rect(screen, bg, self._tri, border_radius=5)
        pygame.draw.rect(screen, PANEL_BORDER, self._tri, 1, border_radius=5)
        cx, cy = self._tri.center
        if self.expanded:        # раскрыто: стрелка вправо (свернуть)
            pts = [(cx - 3, cy - 7), (cx + 4, cy), (cx - 3, cy + 7)]
        else:                    # свёрнуто: стрелка влево (строки выедут влево)
            pts = [(cx + 3, cy - 7), (cx - 4, cy), (cx + 3, cy + 7)]
        pygame.draw.polygon(screen, TEXT_COLOR, pts)

    def _draw_card(self, screen, mouse_pos, offer):
        card = self._card
        draw_plate(screen, card, alpha=225, radius=8)
        stripe = pygame.Rect(card.x + 4, card.y + 6, 4, card.h - 12)
        pygame.draw.rect(screen, lerp_color(offer.color, (255, 255, 255), 0.35), stripe, border_radius=2)
        x = card.x + CARD_PAD + 6
        screen.blit(get_text(offer.title, FONT_SIZE_HEADER, TEXT_COLOR), (x, card.y + CARD_PAD))
        y = card.y + CARD_PAD + CARD_TITLE_H
        for line in self._info_lines:
            screen.blit(get_text(line, FONT_SIZE_LABEL, TEXT_DIM), (x, y))
            y += CARD_LINE_H
        if not offer.replace:
            self.take_button.draw(screen, mouse_pos, colors=ACTIVE_BUTTON_COLORS)
        self.decline_button.draw(screen, mouse_pos)