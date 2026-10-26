"""game/editor/toolbar.py — кнопки редактора карт «Сохранить» и «Выйти» (слой интерфейса, как ToolBar)."""
import pygame

from ui import Button, ACTIVE_BUTTON_COLORS
from ..content import texts

MARGIN = 10
BTN_W, BTN_H = 150, 36
GAP = 8

class EditorBar:
    def __init__(self, on_save, on_exit):
        self.on_save = on_save
        self.on_exit = on_exit
        self.save_button = Button((MARGIN, MARGIN, BTN_W, BTN_H), texts.EDITOR_SAVE)
        self.exit_button = Button((MARGIN, MARGIN + BTN_H + GAP, BTN_W, BTN_H), texts.EDITOR_EXIT)

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        return self.save_button.rect.collidepoint(pos) or self.exit_button.rect.collidepoint(pos)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        if event.type != pygame.MOUSEBUTTONDOWN:
            return False
        if self.save_button.rect.collidepoint(event.pos):
            if event.button == 1 and self.save_button.enabled:
                self.on_save()
            return True                      # любые клики по кнопке поглощаем: в мир они не уйдут
        if self.exit_button.rect.collidepoint(event.pos):
            if event.button == 1:
                self.on_exit()
            return True
        return False

    def draw(self, screen, mouse_pos):
        colors = ACTIVE_BUTTON_COLORS if self.save_button.enabled else None
        self.save_button.draw(screen, mouse_pos, colors=colors)
        self.exit_button.draw(screen, mouse_pos)