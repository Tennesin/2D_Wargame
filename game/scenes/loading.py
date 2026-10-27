"""game/scenes/loading.py — экран загрузки."""
import time
import traceback

import pygame

from engine import get_text, FONT_SIZE_HEADER, FONT_SIZE_LABEL
from ui import draw_plate
from ui.theme import SLIDER_FILL_COLOR, SLIDER_BG_COLOR, TEXT_COLOR, TEXT_DIM
from .base import Scene
from ..content import texts

NO_BACKGROUND = (66, 69, 74)     # серый фон, если снимка меню нет
MARGIN = 36                      # отступ от правого и нижнего краёв окна
BAR_W, BAR_H = 280, 4            # тонкая полоска прогресса
GAP = 8
STEP_BUDGET_S = 0.030            # сколько секунд подряд можно работать до перерисовки

class LoadingScene(Scene):
    BACKGROUND = False           # фон рисуем сами (снимок или серый)

    def __init__(self, task, background, on_done, on_fail, on_quit):
        """task: генератор загрузки; background: размытая картинка или None;
        on_done(scene): всё готово; on_fail(): ошибка в задаче (возврат в меню)."""
        self._task = task
        self._background = background
        self.on_done = on_done
        self.on_fail = on_fail
        self.on_quit = on_quit
        self.progress = 0.0
        self.caption = ""
        self._frames = 0
        self._finished = False

    # ---------- кадр ----------
    def update(self, dt):
        for event in pygame.event.get():             # окно должно отзываться, пока идёт загрузка
            if event.type == pygame.QUIT:
                self.on_quit()
                return
        if self._finished:
            return
        self._frames += 1
        if self._frames == 1:
            return                                   # первый кадр только рисуем: пользователь увидит 0%

        deadline = time.perf_counter() + STEP_BUDGET_S
        try:
            while True:
                try:
                    item = next(self._task)
                except StopIteration as stop:
                    self._finished = True
                    self.progress = 1.0
                    self.on_done(stop.value)
                    return
                starts_stage = self._accept(item)
                if starts_stage or time.perf_counter() >= deadline:
                    return                           # перерисуем кадр, потом продолжим
        except Exception:
            traceback.print_exc()
            self._finished = True
            self.on_fail()

    def _accept(self, item):
        """Разбирает значение yield. Возвращает True, если это начало нового этапа (с подписью)."""
        if isinstance(item, tuple):
            value, self.caption = item
            starts_stage = True
        else:
            value, starts_stage = item, False
        self.progress = max(self.progress, min(1.0, float(value)))
        return starts_stage

    # ---------- рисование ----------
    def _draw_background(self, screen, w, h):
        bg = self._background
        if bg is None:
            screen.fill(NO_BACKGROUND)
            return
        if bg.get_size() != (w, h):                  # окно успели растянуть: подгоняем размытую картинку
            bg = self._background = pygame.transform.scale(bg, (w, h))
        screen.blit(bg, (0, 0))

    def draw(self, screen):
        w, h = screen.get_size()
        self._draw_background(screen, w, h)

        bar = pygame.Rect(w - MARGIN - BAR_W, h - MARGIN - 24, BAR_W, BAR_H)
        title = get_text(texts.LOADING_TITLE, FONT_SIZE_HEADER, TEXT_COLOR)
        percent = get_text(f"{int(self.progress * 100)}%", FONT_SIZE_LABEL, TEXT_DIM)
        caption = get_text(self.caption or " ", FONT_SIZE_LABEL, TEXT_DIM)
        title_rect = title.get_rect(bottomleft=(bar.left, bar.top - GAP))
        percent_rect = percent.get_rect(bottomright=(bar.right, bar.top - GAP))
        caption_rect = caption.get_rect(topright=(bar.right, bar.bottom + GAP))

        draw_plate(screen, title_rect.unionall([bar, caption_rect]).inflate(44, 28), alpha=170)
        screen.blit(title, title_rect)
        screen.blit(percent, percent_rect)
        pygame.draw.rect(screen, SLIDER_BG_COLOR, bar, border_radius=2)
        fill_w = round(BAR_W * self.progress)
        if fill_w > 0:
            pygame.draw.rect(screen, SLIDER_FILL_COLOR, (bar.x, bar.y, fill_w, BAR_H), border_radius=2)
        screen.blit(caption, caption_rect)