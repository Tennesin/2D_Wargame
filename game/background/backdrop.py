"""game/background/backdrop.py — режиссёр фона: КД между событиями, выбор события без недавних повторов,
смена участка карты с затемнением. Ошибка в фоне выключает фон, но не игру."""
import random
import traceback
from collections import deque
from enum import Enum, auto

import pygame

from engine import WORLD
from ui.theme import BG_COLOR
from ..config import BACKGROUND_DIM
from .events import EVENTS, pick_event
from .stage import Stage

COOLDOWN_S = (2.0, 5.0)          # пауза между событиями
FIRST_COOLDOWN_S = (0.8, 1.6)    # пауза перед самым первым
HISTORY = 3                      # столько последних событий не повторяются
FADE_S = 0.35                    # затемнение до чёрного и обратно
RELOCATE_CHANCE = 0.0            # шанс сменить участок карты после события
NEW_WORLD_EVERY = 4              # новую карту (а не другой участок той же) раз в столько событий
EVENT_TIMEOUT_S = 45.0           # страховка: событие дольше этого прерывается
MAX_STEPS = 64                   # страховка от генератора, который не ждёт

class Phase(Enum):
    COOLDOWN = auto()
    EVENT = auto()
    DRAIN = auto()               # событие рассказано: ждём, пока всё уедет и взорвётся
    FADE_OUT = auto()
    FADE_IN = auto()

def _world_key():
    return WORLD.half_w_px, WORLD.half_h_px

class Backdrop:
    def __init__(self, session):
        self.session = session
        self.rng = random.Random()
        self.stage = None
        self.failed = False
        self._history = deque(maxlen=max(0, min(HISTORY, len(EVENTS) - 1)))
        self._phase = Phase.COOLDOWN
        self._timer = 0.0
        self._gen = None
        self._wait = None
        self._event_t = 0.0
        self._fade = 0.0
        self._since_world = 0
        self._first = True
        self._veil = None
        self._world_key = None

    # ==========================================
    # ВНЕШНИЙ ИНТЕРФЕЙС
    # ==========================================
    def update(self, dt, size):
        if self.failed or 0 in size:
            return
        try:
            self._update(dt, size)
        except Exception:
            traceback.print_exc()
            self.failed = True
            self.release()

    def draw(self, screen):
        if self.stage is None:
            screen.fill(BG_COLOR)
            return
        try:
            self.stage.draw(screen)
        except Exception:
            traceback.print_exc()
            self.failed = True
            self.release()
            screen.fill(BG_COLOR)
            return
        alpha = max(BACKGROUND_DIM, int(255 * self._fade))
        if alpha > 0 and self._veil is not None:
            self._veil.set_alpha(min(255, alpha))
            screen.blit(self._veil, (0, 0))

    def release(self):
        """Освободить сцену целиком (кэши спрайтов занимают много памяти). Пересоздастся при следующем update."""
        self.stage = None
        self._gen = None
        self._wait = None
        self._veil = None
        self._phase = Phase.COOLDOWN
        self._first = True

    def play(self, key):
        """Отладка: прервать текущее событие и сразу запустить указанное."""
        if self.stage is None or key not in EVENTS:
            return
        if self._gen is not None:
            self._gen.close()
        self.stage.clear()
        self._history.append(key)
        self._gen = EVENTS[key].run(self.stage)
        self._wait = None
        self._event_t = 0.0
        self._fade = 0.0
        self._phase = Phase.EVENT

    # ==========================================
    # ВНУТРЕННЕЕ
    # ==========================================
    def _make_veil(self, size):
        self._veil = pygame.Surface(size)
        self._veil.fill((0, 0, 0))

    def _build(self, size):
        self.stage = Stage(self.session, size)
        self._world_key = _world_key()
        self._make_veil(size)
        self._gen = None
        self._wait = None
        self._phase = Phase.FADE_IN              # включаемся из чёрного: скрывает подгрузку земли
        self._fade = 1.0

    def _update(self, dt, size):
        if self.stage is not None and self._world_key != _world_key():
            self.release()                       # размер карты поменяли в «Новой игре»
        if self.stage is None:
            self._build(size)
        elif size != self.stage.size:
            self.stage.resize(size)
            self._make_veil(size)
        self.stage.update(dt)

        phase = self._phase
        if phase is Phase.COOLDOWN:
            self._timer -= dt
            if self._timer <= 0.0:
                self._start_event()
        elif phase is Phase.EVENT:
            self._run_event(dt)
        elif phase is Phase.DRAIN:
            self._drain(dt)
        elif phase is Phase.FADE_OUT:
            self._fade_out(dt)
        else:
            self._fade_in(dt)

    # ---------- событие ----------
    def _start_event(self):
        event = pick_event(self._history, self.rng)
        self._history.append(event.key)
        self._gen = event.run(self.stage)
        self._wait = None
        self._event_t = 0.0
        self._phase = Phase.EVENT

    def _run_event(self, dt):
        self._event_t += dt
        if self._event_t > EVENT_TIMEOUT_S:
            self._abort()
            return
        try:
            self._advance(dt)
        except Exception:                        # ошибка в одном событии не должна ронять фон
            traceback.print_exc()
            self._abort()

    def _advance(self, dt):
        """Двигает генератор события: число = пауза в секундах, функция = ждать, пока вернёт True."""
        budget = dt
        for _ in range(MAX_STEPS):
            wait = self._wait
            if wait is not None:
                if callable(wait):
                    if not wait():
                        return
                    budget = 0.0
                else:
                    wait -= budget
                    if wait > 0.0:
                        self._wait = wait
                        return
                    budget = -wait               # остаток времени переносим дальше: паузы не копят ошибку
                self._wait = None
            try:
                nxt = next(self._gen)
            except StopIteration:
                self._gen = None
                self._phase = Phase.DRAIN
                return
            self._wait = nxt if callable(nxt) else float(nxt or 0.0)

    def _drain(self, dt):
        self._event_t += dt
        if self.stage.quiet():
            self._finish()
        elif self._event_t > EVENT_TIMEOUT_S:
            self.stage.clear()
            self._finish()

    def _abort(self):
        if self._gen is not None:
            self._gen.close()
            self._gen = None
        self.stage.clear()
        self._finish()

    def _finish(self):
        self._since_world += 1
        if RELOCATE_CHANCE > 0.0 and self.rng.random() < RELOCATE_CHANCE:
            self._phase = Phase.FADE_OUT
        else:
            self._start_cooldown()

    # ---------- затемнение и смена участка ----------
    def _fade_out(self, dt):
        self._fade = min(1.0, self._fade + dt / FADE_S)
        if self._fade >= 1.0:
            new_world = self._since_world >= NEW_WORLD_EVERY
            if new_world:
                self._since_world = 0
            self.stage.clear()
            self.stage.relocate(new_world)       # экран чёрный: подгрузка земли незаметна
            self._phase = Phase.FADE_IN

    def _fade_in(self, dt):
        self._fade = max(0.0, self._fade - dt / FADE_S)
        if self._fade <= 0.0:
            self._start_cooldown()

    def _start_cooldown(self):
        lo, hi = FIRST_COOLDOWN_S if self._first else COOLDOWN_S
        self._first = False
        self._timer = self.rng.uniform(lo, hi)
        self._phase = Phase.COOLDOWN