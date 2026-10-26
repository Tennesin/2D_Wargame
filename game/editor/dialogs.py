"""game/editor/dialogs.py — модальное окно редактора: сообщение, поле ввода и кнопки.
Это слой интерфейса, который стоит в InputHandler первым: пока окно открыто, оно забирает все события."""
import pygame

from engine import AlphaLayer, get_text, get_font, wrap_text, FONT_SIZE_HEADER, FONT_SIZE_LABEL
from ui import Button, TextInput, draw_plate
from ui.theme import TEXT_COLOR, TEXT_DIM
from ..content import texts

W = 560
PAD = 20
TITLE_H = 34
LINE_H = 22
INPUT_H = 40
BTN_H = 44
GAP = 12
DIM_ALPHA = 150

class Dialog:
    def __init__(self):
        self.active = False
        self.title = ""
        self.lines = []
        self.input = None                # TextInput или None
        self.buttons = []                # [(Button, колбэк, цвета, нужен_текст)]
        self._default = 0
        self._rect = pygame.Rect(0, 0, W, 100)
        self._alpha = AlphaLayer()

    # ---------- открытие и закрытие ----------
    def open(self, title, message, buttons, text=None, max_len=40, default=0):
        """buttons: [(подпись, колбэк или None, цвета или None, нужен_ли_текст), ...].
        Последняя кнопка считается «Отменой»: на неё нажимает Esc. Enter нажимает кнопку default.
        text: None: поля ввода нет; строка: поле с таким начальным текстом, и колбэки получают введённое."""
        self.title = title
        self.lines = wrap_text(get_font(FONT_SIZE_LABEL), message, W - 2 * PAD)
        self.input = None if text is None else TextInput((0, 0, W - 2 * PAD, INPUT_H), text, max_len,
                                                         texts.EDITOR_NAME_HINT)
        self.buttons = [(Button((0, 0, 10, BTN_H), label), cb, colors, need)
                        for label, cb, colors, need in buttons]
        self._default = default
        self.active = True
        pygame.key.set_repeat(400, 40)           # удержание Backspace и стрелок
        self._layout()

    def close(self):
        self.active = False
        pygame.key.set_repeat()                  # без аргументов: повтор клавиш выключен

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        return self.active

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        if not self.active or event.type == pygame.QUIT:
            return False                         # закрытие окна приложения не блокируем
        self._layout()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._press(len(self.buttons) - 1)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._press(self._default)
            elif self.input is not None:
                self.input.handle_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, (button, _, _, _) in enumerate(self.buttons):
                if button.collidepoint(event.pos):
                    self._press(i)
                    break
        return True

    # ---------- внутреннее ----------
    def _press(self, index):
        _, callback, _, need_text = self.buttons[index]
        text = self.input.text.strip() if self.input is not None else None
        if need_text and not text:
            return
        self.close()                             # сначала закрываем: колбэк может открыть следующее окно
        if callback is not None:
            callback() if text is None else callback(text)

    def _layout(self):
        w, h = pygame.display.get_surface().get_size()
        height = PAD + TITLE_H + len(self.lines) * LINE_H + GAP
        if self.input is not None:
            height += INPUT_H + GAP
        height += BTN_H + PAD
        rect = pygame.Rect(0, 0, W, height)
        rect.center = (w // 2, h // 2)
        self._rect = rect

        y = rect.y + PAD + TITLE_H + len(self.lines) * LINE_H + GAP
        if self.input is not None:
            self.input.rect.topleft = (rect.x + PAD, y)
            y += INPUT_H + GAP
        n = len(self.buttons)
        bw = (W - 2 * PAD - GAP * (n - 1)) // n
        has_text = self.input is None or bool(self.input.text.strip())
        for i, (button, _, _, need_text) in enumerate(self.buttons):
            button.rect = pygame.Rect(rect.x + PAD + i * (bw + GAP), y, bw, BTN_H)
            button.enabled = has_text or not need_text

    def draw(self, screen, mouse_pos):
        if not self.active:
            return
        self._layout()
        layer = self._alpha.begin(screen.get_size())
        layer.fill((0, 0, 0, DIM_ALPHA))
        screen.blit(layer, (0, 0))

        rect = self._rect
        draw_plate(screen, rect, alpha=245)
        screen.blit(get_text(self.title, FONT_SIZE_HEADER, TEXT_COLOR), (rect.x + PAD, rect.y + PAD))
        y = rect.y + PAD + TITLE_H
        for line in self.lines:
            screen.blit(get_text(line, FONT_SIZE_LABEL, TEXT_DIM), (rect.x + PAD, y))
            y += LINE_H
        if self.input is not None:
            self.input.draw(screen, mouse_pos)
        for button, _, colors, _ in self.buttons:
            button.draw(screen, mouse_pos, colors=colors)