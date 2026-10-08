"""keymap.py — действия игрока и привязки клавиш. Единственное место, где перечислены клавиши."""
from enum import Enum, auto

import pygame

class Action(Enum):
    # удерживаемые
    FORWARD = auto()
    BACKWARD = auto()
    LEFT = auto()
    RIGHT = auto()
    ZOOM_IN = auto()
    ZOOM_OUT = auto()
    # разовые
    CANCEL = auto()
    TOGGLE_DEBUG = auto()
    LOCK_TURRET = auto()
    TOGGLE_BUILD = auto()
    TOGGLE_FREE_CAM = auto()
    DELETE_WALL = auto()
    # боевое состояние: есть и в HELD_KEYMAP, и в PRESS_KEYMAP, Game выбирает по COMBAT_HOLD
    COMBAT = auto()


class MouseOwner(Enum):
    """Кому сейчас принадлежит нажатая кнопка мыши (до её отпускания)."""
    UI = auto()       # интерфейс: ползунок, кнопка, панель
    ROTATE = auto()   # вращение выбранной стены за белую точку
    FIRE = auto()     # удержание ЛКМ в мире при включённом боевом состоянии
    PAN = auto()      # перетаскивание камеры зажатой ПКМ (свободная камера)

# False: Alt переключает боевое состояние нажатием. True: боевое состояние, пока Alt зажат.
COMBAT_HOLD = False

# Удерживаемые действия: действие -> клавиши, любая из которых его включает
HELD_KEYMAP = {
    Action.FORWARD:  (pygame.K_w, pygame.K_UP),
    Action.BACKWARD: (pygame.K_s, pygame.K_DOWN),
    Action.LEFT:     (pygame.K_a, pygame.K_LEFT),
    Action.RIGHT:    (pygame.K_d, pygame.K_RIGHT),
    Action.ZOOM_IN:  (pygame.K_EQUALS, pygame.K_KP_PLUS, pygame.K_PAGEUP),
    Action.ZOOM_OUT: (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_PAGEDOWN),
    Action.COMBAT:   (pygame.K_LALT, pygame.K_RALT),
}

# Разовые действия: действие -> клавиши
PRESS_KEYMAP = {
    Action.CANCEL:       (pygame.K_ESCAPE,),
    Action.TOGGLE_DEBUG: (pygame.K_TAB,),     # Tab: отладочные строки
    Action.LOCK_TURRET:  (pygame.K_q,),
    Action.TOGGLE_BUILD: (pygame.K_b,),
    Action.TOGGLE_FREE_CAM: (pygame.K_l,),
    Action.DELETE_WALL:  (pygame.K_DELETE,),
    Action.COMBAT:       (pygame.K_LALT, pygame.K_RALT),
}

# Обратная таблица для быстрого поиска по событию KEYDOWN: клавиша -> действие
KEY_TO_PRESS = {key: action for action, keys in PRESS_KEYMAP.items() for key in keys}