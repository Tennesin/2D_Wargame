"""ui/ammo_bar.py — столбик кнопок выбора снаряда справа от мини-панели игрока.
О танках не знает: что показывать и что делать по клику, приходит снаружи."""
import pygame

from engine import get_text
from .theme import BUTTON_COLORS, PANEL_BORDER, TEXT_COLOR, TEXT_DIM
from .hud import MARGIN, WIDTH, HEIGHT
from .ammo_icons import make_ammo_icon

BTN = 44                    # сторона кнопки; 3 кнопки + 2 зазора = HEIGHT мини-панели
GAP = 6
OFFSET_X = 8                # зазор между мини-панелью и столбиком
ICON_SIZE = (28, 16)
SELECT_COLOR = (90, 200, 90)    # зелёная рамка выбранного снаряда
CODE_SIZE = 14
KEY_SIZE = 12

class AmmoBar:
    def __init__(self, items, on_select):
        """items — [(ключ снаряда, двухбуквенный код, подпись клавиши), ...]; on_select(ключ)."""
        self.items = items
        self.on_select = on_select
        self.rects = [pygame.Rect(0, 0, BTN, BTN) for _ in items]
        self._icons = {kind: make_ammo_icon(kind, ICON_SIZE) for kind, _, _ in items}
        self._size = None
        self.update(pygame.display.get_surface().get_size())

    def update(self, screen_size):
        """Раскладка пересчитывается только при смене размера окна."""
        if screen_size == self._size:
            return
        self._size = screen_size
        x = MARGIN + WIDTH + OFFSET_X
        y = screen_size[1] - MARGIN - HEIGHT
        for rect in self.rects:
            rect.topleft = (x, y)
            y += BTN + GAP

    # ---------- интерфейс слоя (как у ToolBar) ----------
    def covers(self, pos):
        return any(r.collidepoint(pos) for r in self.rects)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN:
            for (kind, _, _), rect in zip(self.items, self.rects):
                if rect.collidepoint(event.pos):
                    if event.button == 1:
                        self.on_select(kind)
                    return True              # любые клики по кнопке поглощаем: выстрела не будет
        return False

    def draw(self, screen, mouse_pos, selected):
        for (kind, code, key), rect in zip(self.items, self.rects):
            bg = BUTTON_COLORS["hover"] if rect.collidepoint(mouse_pos) else BUTTON_COLORS["normal"]
            pygame.draw.rect(screen, bg, rect, border_radius=5)
            if kind is selected:
                pygame.draw.rect(screen, SELECT_COLOR, rect, 3, border_radius=5)
            else:
                pygame.draw.rect(screen, PANEL_BORDER, rect, 1, border_radius=5)

            icon = self._icons[kind]
            screen.blit(icon, icon.get_rect(midtop=(rect.centerx - 3, rect.y + 11)))
            code_s = get_text(code, CODE_SIZE, TEXT_COLOR)
            screen.blit(code_s, code_s.get_rect(midbottom=(rect.centerx, rect.bottom - 3)))
            key_s = get_text(key, KEY_SIZE, TEXT_DIM)
            screen.blit(key_s, key_s.get_rect(topright=(rect.right - 4, rect.y + 2)))