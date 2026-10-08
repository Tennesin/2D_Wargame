"""ui/toolbar.py — панель инструментов в левом верхнем углу."""
import pygame

from .theme import TOOLBAR_MARGIN, TOOLBAR_BUTTON_SIZE, BUTTON_COLORS, ACTIVE_BUTTON_COLORS
from .widgets import Button

class ToolBar:
    def __init__(self):
        self.on_create_wall = None           # колбэк нажатия кнопки
        self.active = False
        self.wall_button = Button((TOOLBAR_MARGIN, TOOLBAR_MARGIN, *TOOLBAR_BUTTON_SIZE), "Создать стену")

    def set_active(self, active):
        self.active = active
        self.wall_button.label = "Отмена" if active else "Создать стену"

    def covers(self, pos):
        """Лежит ли точка экрана на кнопке панели инструментов."""
        return self.wall_button.rect.collidepoint(pos)

    def cancel_drag(self):
        """У кнопки нет перетаскивания; метод нужен ради общего интерфейса слоёв."""
        pass

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and self.wall_button.collidepoint(event.pos):
            if event.button == 1 and self.on_create_wall:
                self.on_create_wall()
            return True                      # любые клики по кнопке поглощаем
        return False

    def draw(self, screen, mouse_pos):
        colors = ACTIVE_BUTTON_COLORS if self.active else BUTTON_COLORS
        self.wall_button.draw(screen, mouse_pos, colors=colors)