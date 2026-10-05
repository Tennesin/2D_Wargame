"""controls.py — действия игрока и привязки клавиш. Единственное место, где перечислены клавиши."""
from enum import Enum, auto

import pygame

class Action(Enum):
    # удерживаемые (движение)
    FORWARD = auto()
    BACKWARD = auto()
    LEFT = auto()
    RIGHT = auto()
    # разовые (нажали -> сработало один раз)
    CANCEL = auto()
    TOGGLE_DEBUG = auto()
    LOCK_TURRET = auto()


# Удерживаемые действия: действие -> клавиши, любая из которых его включает
HELD_KEYMAP = {
    Action.FORWARD:  (pygame.K_w, pygame.K_UP),
    Action.BACKWARD: (pygame.K_s, pygame.K_DOWN),
    Action.LEFT:     (pygame.K_a, pygame.K_LEFT),
    Action.RIGHT:    (pygame.K_d, pygame.K_RIGHT),
}

# Разовые действия: действие -> клавиши
PRESS_KEYMAP = {
    Action.CANCEL:       (pygame.K_ESCAPE,),
    Action.TOGGLE_DEBUG: (pygame.K_F3,),
    Action.LOCK_TURRET:  (pygame.K_q,),   # переключает слежение башни за мышью
}

# Обратная таблица для быстрого поиска по событию KEYDOWN: клавиша -> действие
KEY_TO_PRESS = {key: action for action, keys in PRESS_KEYMAP.items() for key in keys}

# Зум с клавиатуры (временно, до этапа 5): модификатор + стрелки
ZOOM_MODIFIER = pygame.K_LCTRL
ZOOM_IN_KEY = pygame.K_UP
ZOOM_OUT_KEY = pygame.K_DOWN
# Пока зажат модификатор зума, эти клавиши не считаются движением
KEYS_BLOCKED_BY_ZOOM_MODIFIER = (pygame.K_UP, pygame.K_DOWN)