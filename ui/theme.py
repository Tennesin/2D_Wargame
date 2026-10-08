"""ui/theme.py — размеры и цвета интерфейса."""

PANEL_WIDTH = 340
PANEL_PADDING = 14
HEADER_HEIGHT = 56           # высота шапки панели (под заголовок и красную кнопку)
SCROLLBAR_GAP = 12           # место справа от контента под полосу прокрутки
TOGGLE_SIZE = 36
TOGGLE_MARGIN = 6
DEFAULT_SCROLL_SPEED = 30

PANEL_BG = (28, 31, 36, 235)         # RGBA, чуть прозрачный фон
PANEL_BORDER = (70, 76, 86)
TEXT_COLOR = (230, 230, 230)
TEXT_DIM = (150, 156, 166)
LINE_COLOR = (62, 68, 78)

BUTTON_COLORS = {
    "normal": (60, 66, 76), "hover": (80, 88, 100),
    "disabled": (40, 42, 46), "text": (235, 235, 235),
}
TOGGLE_COLORS = {                    # красный прямоугольник-переключатель
    "normal": (200, 40, 40), "hover": (235, 70, 70),
    "disabled": (90, 40, 40), "text": (255, 255, 255),
}
SLIDER_FILL_COLOR = (200, 140, 60)
SLIDER_BG_COLOR = (45, 49, 56)
SLIDER_BORDER_COLOR = (90, 96, 106)

TOOLBAR_MARGIN = 6
TOOLBAR_BUTTON_SIZE = (150, 36)
ACTIVE_BUTTON_COLORS = {             # кнопка «Создать стену», пока включён режим стройки
    "normal": (200, 140, 60), "hover": (225, 165, 85),
    "disabled": (90, 70, 40), "text": (30, 30, 30),
}
DELETE_BUTTON_COLORS = {             # красная кнопка «Удалить стену»
    "normal": (190, 45, 45), "hover": (225, 75, 75),
    "disabled": (80, 40, 40), "text": (255, 255, 255),
}