"""ui/panel.py — панель конструктора: прокрутка, раскладка, события."""
import pygame

from engine import FONT_SIZE_TITLE, get_text
from .theme import (PANEL_WIDTH, PANEL_PADDING, HEADER_HEIGHT, SCROLLBAR_GAP,
                    PANEL_BG, PANEL_BORDER, TEXT_COLOR)
from .widgets import ScrollArea, ParamRow, StatsBlock, ActionButton, ChoiceRow

class Panel:
    """Содержимое одной панели: заголовок, элементы и колбэк «ползунок сдвинут»."""

    def __init__(self, title, items, on_change=None):
        self.title = title
        self.items = items
        self.on_change = on_change       # функция(values: dict) или None

    def get_values(self):
        """Текущие значения всех ползунков и переключателей панели: {ключ: значение}."""
        return {it.key: it.value for it in self.items if isinstance(it, (ParamRow, ChoiceRow))}

    def set_values(self, values):
        """Поставить значения извне (без вызова on_change)."""
        for it in self.items:
            if isinstance(it, (ParamRow, ChoiceRow)) and it.key in values:
                it.set_value(values[it.key])

    def set_enabled(self, key, enabled):
        """Включить или выключить переключатель с ключом key."""
        for it in self.items:
            if isinstance(it, ChoiceRow) and it.key == key:
                it.enabled = enabled
                return

    def set_options(self, key, options):
        """Сменить варианты переключателя key. Возвращает True, если что-то изменилось."""
        for it in self.items:
            if isinstance(it, ChoiceRow) and it.key == key:
                return it.set_options(options)
        return False

    def set_range(self, key, lo, hi):
        """Сменить границы ползунка с ключом key (без вызова on_change)."""
        for it in self.items:
            if isinstance(it, ParamRow) and it.key == key:
                it.set_range(lo, hi)
                return

class SidePanel:
    def __init__(self, screen_size, panels, start_mode, *, start_open=False):
        self.screen_size = screen_size
        self.is_open = start_open
        self.panels = panels
        self.mode = start_mode

        self.scroll = ScrollArea()
        self.panel_rect = pygame.Rect(0, 0, PANEL_WIDTH, 0)
        self.content_rect = pygame.Rect(0, 0, 0, 0)
        self._bg_surface = None
        self._active_row = None          # строка, ползунок которой сейчас тянут

        self._stat_blocks = {}           # (режим, название) -> StatsBlock
        self._index_stats()
        self._layout()

    @property
    def items(self):
        """Элементы показанной сейчас панели."""
        return self.panels[self.mode].items

    # ---------- публичный интерфейс ----------
    def set_on_change(self, mode, callback):
        """Колбэк «ползунок панели mode сдвинут»: функция(values: dict)."""
        self.panels[mode].on_change = callback

    def get_values(self, mode=None):
        """Значения ползунков панели mode (по умолчанию показанной): {ключ: число}."""
        return self.panels[self.mode if mode is None else mode].get_values()

    def set_values(self, mode, values):
        self.panels[mode].set_values(values)

    def set_range(self, mode, key, lo, hi):
        """Границы ползунка key на панели mode. Высота строки не меняется, перекладывать панель не нужно."""
        self.panels[mode].set_range(key, lo, hi)

    def set_enabled(self, mode, key, enabled):
        """Доступность переключателя key на панели mode."""
        self.panels[mode].set_enabled(key, enabled)

    def set_choice_options(self, mode, key, options):
        """Варианты переключателя key на панели mode (например, «Щучий» или «Клин» по массе)."""
        if self.panels[mode].set_options(key, options) and mode == self.mode:
            self._layout()

    def _index_stats(self):
        """Один раз связывает (режим, название характеристики) с блоком, где она показана."""
        for mode, panel in self.panels.items():
            for it in panel.items:
                if isinstance(it, StatsBlock):
                    for name in it.values:
                        self._stat_blocks[(mode, name)] = it

    def set_stat(self, mode, name, value):
        """Записать рассчитанную характеристику в блок статистики панели mode."""
        block = self._stat_blocks.get((mode, name))
        if block is not None:
            block.values[name] = value

    def show(self, mode, values=None):
        """Показать панель mode и открыть её."""
        if values is not None:
            self.set_values(mode, values)
        self._switch(mode)
        self.open()

    def _switch(self, mode):
        self.mode = mode
        self._active_row = None
        self.scroll.offset = 0
        self._layout()

    def open(self):
        if not self.is_open:
            self.is_open = True
            self._active_row = None

    def close(self):
        if self.is_open:
            self.is_open = False
            self._active_row = None

    def update(self, screen_size):
        """Вызывать каждый кадр, но раскладка пересчитывается только при смене размера окна.
        Остальные поводы (прокрутка, смена панели) вызывают _layout() сами."""
        if screen_size != self.screen_size:
            self.screen_size = screen_size
            self._layout()

    def covers(self, pos):
        """Лежит ли точка экрана на открытой панели."""
        return self.is_open and self.panel_rect.collidepoint(pos)

    def cancel_drag(self):
        """Бросить перетаскивание ползунка (кнопку отпустили, а событие до нас не дошло)."""
        self._active_row = None

    # ---------- раскладка ----------
    def _layout(self):
        w, h = self.screen_size
        self.panel_rect = pygame.Rect(w - PANEL_WIDTH, 0, PANEL_WIDTH, h)
        self.content_rect = pygame.Rect(
            self.panel_rect.x + PANEL_PADDING,
            HEADER_HEIGHT,
            PANEL_WIDTH - 2 * PANEL_PADDING,
            max(0, h - HEADER_HEIGHT - PANEL_PADDING),
        )

        inner_w = self.content_rect.width - SCROLLBAR_GAP
        # высота некоторых элементов (InfoText) зависит от ширины — сначала layout, потом границы
        y = self.content_rect.y
        total = 0
        for it in self.items:
            it.layout(self.content_rect.x, y, inner_w)
            y += it.height
            total += it.height
        self.scroll.update_bounds(total, self.content_rect.height)

        y = self.content_rect.y - self.scroll.offset
        for it in self.items:
            it.layout(self.content_rect.x, y, inner_w)
            y += it.height

    # ---------- события ----------
    def handle_event(self, event, mouse_pos):
        """Возвращает True, если событие поглощено интерфейсом."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_open and self.panel_rect.collidepoint(event.pos):
                if event.button == 1 and self.content_rect.collidepoint(event.pos):
                    for it in self.items:
                        if isinstance(it, ParamRow) and it.hit_rect().collidepoint(event.pos):
                            self._active_row = it
                            self._drag_slider(event.pos[0])
                            break
                        if isinstance(it, ActionButton) and it.hit(event.pos):
                            it.click()
                            break
                        if isinstance(it, ChoiceRow):
                            choice = it.hit(event.pos)
                            if choice is not None:
                                self._choose(it, choice)
                                break
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._active_row is not None:
                self._drag_slider(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._active_row is not None:
                self._active_row = None
                return True

        elif event.type == pygame.MOUSEWHEEL:
            if self.is_open and self.panel_rect.collidepoint(mouse_pos):
                self.scroll.scroll_by_wheel(event.y)
                self._layout()
                return True

        return False

    def _drag_slider(self, mouse_x):
        if self._active_row.slider.set_from_mouse(mouse_x):
            self._notify_change()

    def _choose(self, row, choice):
        if choice != row.value:
            row.value = choice
            self._notify_change()

    def _notify_change(self):
        panel = self.panels[self.mode]
        if panel.on_change:
            panel.on_change(panel.get_values())

    # ---------- отрисовка ----------
    def draw(self, screen, mouse_pos):
        if self.is_open:
            self._draw_panel(screen, mouse_pos)

    def _draw_panel(self, screen, mouse_pos):
        rect = self.panel_rect
        if self._bg_surface is None or self._bg_surface.get_size() != rect.size:
            self._bg_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            self._bg_surface.fill(PANEL_BG)
        screen.blit(self._bg_surface, rect.topleft)
        pygame.draw.line(screen, PANEL_BORDER, rect.topleft, rect.bottomleft, 2)

        title = get_text(self.panels[self.mode].title, FONT_SIZE_TITLE, TEXT_COLOR)
        screen.blit(title, (rect.x + PANEL_PADDING, 16))

        # содержимое рисуем с обрезкой, чтобы при прокрутке оно не вылезало за панель
        screen.set_clip(self.content_rect)
        for it in self.items:
            if it.rect.colliderect(self.content_rect):
                it.draw(screen, mouse_pos)
        screen.set_clip(None)

        self.scroll.draw_scrollbar(screen, self.content_rect)