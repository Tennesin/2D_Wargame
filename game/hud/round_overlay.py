"""game/hud/round_overlay.py — единая плашка над панелью танка: номер раунда, враги и таймер."""
import math

import pygame

from engine import get_text, FONT_SIZE_LABEL
from ui import draw_plate
from ui.tank_panel import panel_rect
from ui.theme import TEXT_COLOR, LINE_COLOR
from ..content import texts
from ..match.rounds.spawner import RoundPhase

GAP = 8                      # зазор между плашкой и панелью танка
BLOCK_H = 30                 # высота плашки
PAD_X = 7                    # внутренний отступ каждой секции по бокам
CLOCK_R = 7                  # радиус значка часов
CLOCK_GAP = 5                # зазор между часами и числом
DIV_INSET = 6                # разделители не доходят до верха и низа плашки
LOW_TIME_S = 10              # столько секунд до конца раунда и меньше: время красное

C_WARN = (240, 210, 70)
C_BAD = (230, 80, 70)

def block_top(size):
    """Верхняя граница плашки для окна size. Её читает DebugOverlay, чтобы правая колонка не лезла под плашку."""
    return panel_rect(size).top - GAP - BLOCK_H

class RoundOverlay:
    def __init__(self, spawner, player):
        self.spawner = spawner
        self.player = player

    def draw(self, screen):
        sp = self.spawner
        if sp.round == 0 or not self.player.alive:
            return

        countdown = sp.phase is RoundPhase.COUNTDOWN

        # --- тексты и цвета ---
        round_s = get_text(texts.ROUND_LABEL.format(n=sp.round), FONT_SIZE_LABEL, TEXT_COLOR)

        alive = "–" if countdown else str(sp.group_alive)      # в отсчёте группы ещё нет на карте
        bots_s = get_text(f"{alive}/{sp.group_total}", FONT_SIZE_LABEL, TEXT_COLOR)

        if countdown and (sp.waiting_for_room or sp.time_left <= 0.0):
            time_text = texts.ROUND_NO_TIME
        else:
            time_text = texts.ROUND_TIME_FMT.format(t=math.ceil(sp.time_left))
        if countdown:
            time_color = C_WARN
        elif sp.time_left <= LOW_TIME_S:
            time_color = C_BAD
        else:
            time_color = TEXT_COLOR
        time_s = get_text(time_text, FONT_SIZE_LABEL, time_color)

        # --- ширины секций (у чисел и времени ширина зарезервирована, чтобы плашка не дёргалась) ---
        bots_ref = get_text("8/8", FONT_SIZE_LABEL, TEXT_COLOR).get_width()
        time_ref = get_text(texts.ROUND_TIME_FMT.format(t=888), FONT_SIZE_LABEL, TEXT_COLOR).get_width()
        w_round = round_s.get_width() + 2 * PAD_X
        w_bots = max(bots_ref, bots_s.get_width()) + 2 * PAD_X
        w_time = 2 * CLOCK_R + CLOCK_GAP + max(time_ref, time_s.get_width()) + 2 * PAD_X

        # --- общий прямоугольник над панелью танка, правый край совпадает с её правым краем ---
        panel = panel_rect(screen.get_size())
        rect = pygame.Rect(0, 0, w_round + w_bots + w_time, BLOCK_H)
        rect.bottomright = (panel.right, panel.top - GAP)
        draw_plate(screen, rect, alpha=205, radius=8)

        cy = rect.centery
        x = rect.x

        # секция 1: Round: X
        screen.blit(round_s, round_s.get_rect(center=(x + w_round // 2, cy)))
        x += w_round
        self._divider(screen, x, rect)

        # секция 2: живые / всего
        screen.blit(bots_s, bots_s.get_rect(center=(x + w_bots // 2, cy)))
        x += w_bots
        self._divider(screen, x, rect)

        # секция 3: часы и время
        self._draw_clock(screen, x + PAD_X + CLOCK_R, cy, CLOCK_R, time_color)
        screen.blit(time_s, time_s.get_rect(midleft=(x + PAD_X + 2 * CLOCK_R + CLOCK_GAP, cy)))

    @staticmethod
    def _divider(screen, x, rect):
        pygame.draw.line(screen, LINE_COLOR, (x, rect.y + DIV_INSET), (x, rect.bottom - DIV_INSET), 1)

    @staticmethod
    def _draw_clock(screen, cx, cy, r, color):
        """Значок часов: кольцо и две стрелки."""
        pygame.draw.circle(screen, color, (cx, cy), r, 2)
        pygame.draw.line(screen, color, (cx, cy), (cx, cy - r + 3), 2)          # минутная
        pygame.draw.line(screen, color, (cx, cy), (cx + r - 4, cy + 1), 2)      # часовая