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
    COMBAT = auto()
    AMMO_1 = auto()
    AMMO_2 = auto()
    AMMO_3 = auto()
    REPAIR = auto()
    SNAPSHOT = auto()

class MouseOwner(Enum):
    """Кому сейчас принадлежит нажатая кнопка мыши (до её отпускания)."""
    UI = auto()       # интерфейс: ползунок, кнопка, панель
    ROTATE = auto()   # вращение выбранной стены за белую точку
    FIRE = auto()     # удержание ЛКМ в мире при включённом боевом состоянии
    PAN = auto()      # перетаскивание камеры зажатой ПКМ (свободная камера)

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
    Action.CANCEL:          (pygame.K_ESCAPE,),
    Action.TOGGLE_DEBUG:    (pygame.K_TAB,),
    Action.LOCK_TURRET:     (pygame.K_q,),
    Action.TOGGLE_BUILD:    (pygame.K_b,),
    Action.TOGGLE_FREE_CAM: (pygame.K_l,),
    Action.DELETE_WALL:     (pygame.K_DELETE,),
    Action.COMBAT:          (pygame.K_LALT, pygame.K_RALT),
    Action.AMMO_1:          (pygame.K_1, pygame.K_KP1),
    Action.AMMO_2:          (pygame.K_2, pygame.K_KP2),
    Action.AMMO_3:          (pygame.K_3, pygame.K_KP3),
    Action.REPAIR:          (pygame.K_r,),
    Action.SNAPSHOT:        (pygame.K_v,),
}

# Обратная таблица для быстрого поиска по событию KEYDOWN: клавиша -> действие
KEY_TO_PRESS = {key: action for action, keys in PRESS_KEYMAP.items() for key in keys}
# порядок совпадает с vehicles.AMMO_ORDER: ББ, КС, ФГ
AMMO_HOTKEYS = (Action.AMMO_1, Action.AMMO_2, Action.AMMO_3)
# Подписи клавиш для подсказок на экране. Нет в словаре: берём имя из pygame.
KEY_LABELS = {pygame.K_LALT: "Alt", pygame.K_RALT: "Alt", pygame.K_ESCAPE: "Esc",
              pygame.K_DELETE: "Delete", pygame.K_TAB: "Tab"}

def key_label(action):
    """Подпись первой клавиши действия (для подсказок, чтобы не писать «Alt» или «L» руками)."""
    codes = PRESS_KEYMAP.get(action) or HELD_KEYMAP[action]
    return KEY_LABELS.get(codes[0]) or pygame.key.name(codes[0]).upper()