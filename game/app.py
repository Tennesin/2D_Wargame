"""game/app.py — окно, главный цикл и смена сцен. Логики игры здесь нет."""
import sys
import pygame

from .config import GAME_TITLE, BACKGROUND_ENABLED
from .background import Backdrop
from .scenes import (
    MenuScene, ConstructorScene, PlayScene,
    SettingsScene, InstructionScene, NewGameScene, StatsScene, ResultScene,
)
from .state.session import Session
from ui.theme import BG_COLOR

def _maximize_window():
    """Разворачивает окно на весь экран, как кнопка «Развернуть» (рамка и кнопки окна остаются).
    Сначала штатный способ pygame 2, запасной вариант для Windows через WinAPI."""
    try:
        from pygame._sdl2.video import Window
        Window.from_display_module().maximize()
        return
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info()["window"]
            ctypes.windll.user32.ShowWindow(hwnd, 3)     # 3 = SW_MAXIMIZE
        except Exception:
            pass                                          # не вышло: останется обычное окно

class App:
    MAX_DT = 0.05   # защита от «телепорта» при подвисании окна

    def __init__(self, seed=None):
        pygame.init()
        pygame.display.set_mode((1000, 700), pygame.RESIZABLE)   # размер «восстановленного» окна
        pygame.display.set_caption(GAME_TITLE)
        _maximize_window()
        pygame.event.pump()                                      # применить новый размер до создания меню
        self.clock = pygame.time.Clock()
        self.seed = seed                 # None: у каждой новой игры свой случайный мир
        self.session = Session()         # настройки техники живут здесь, пока открыто приложение
        self.backdrop = Backdrop(self.session)   # фоновая симуляция (создаётся лениво, при первом показе)

        self.running = True
        self.scene = None
        self._next = None                # функция, создающая следующую сцену (применяется в конце кадра)

        self.show_menu()
        self._apply_pending()

    # ---------- смена сцен (их передают сценам как колбэки) ----------
    def show_menu(self):
        self._next = lambda: MenuScene(
            on_play=self.show_newgame,
            on_constructor=self.show_constructor,
            on_instruction=self.show_instruction,
            on_settings=self.show_settings,
            on_stats=self.show_stats,
            on_quit=self.quit)

    def show_newgame(self):
        self._next = lambda: NewGameScene(self.session, on_play=self.start_game,
                                          on_constructor=self.show_constructor,
                                          on_back=self.show_menu, on_quit=self.quit)

    def show_constructor(self):
        self._next = lambda: ConstructorScene(self.session, on_play=self.show_newgame,
                                              on_menu=self.show_menu, on_quit=self.quit)

    def show_settings(self):
        self._next = lambda: SettingsScene(self.session.settings,
                                           on_back=self.show_menu, on_quit=self.quit)

    def show_instruction(self):
        self._next = lambda: InstructionScene(on_back=self.show_menu, on_quit=self.quit)

    def show_stats(self):
        self._next = lambda: StatsScene(self.session.career, on_back=self.show_menu, on_quit=self.quit)

    def show_result(self, stats):
        self._next = lambda: ResultScene(stats, self.session.career, on_again=self.show_newgame,
                                         on_menu=self.show_menu, on_quit=self.quit)

    def start_game(self):
        self._next = lambda: PlayScene(self.seed, self.clock, self.session,
                                       on_result=self.show_result, on_quit=self.quit)

    def quit(self):
        self.running = False

    def _apply_pending(self):
        """Сцену подменяем только между кадрами, а не посреди её собственного update."""
        if self._next is not None:
            factory, self._next = self._next, None
            self.scene = factory()

    def _update_background(self, dt, screen):
        """Фон под сценой: симуляция или (если выключена) плоская заливка. Сцены с BACKGROUND = False
        рисуют всё сами. Партия освобождает фон полностью, остальные сцены только ставят его на паузу."""
        scene = self.scene
        if scene.FREE_BACKGROUND:
            self.backdrop.release()
        if not scene.BACKGROUND:
            return
        if BACKGROUND_ENABLED:
            self.backdrop.update(dt, screen.get_size())
            self.backdrop.draw(screen)
        else:
            screen.fill(BG_COLOR)

    # ---------- цикл ----------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(self.session.settings.fps_limit) / 1000.0, self.MAX_DT)
            self.scene.update(dt)

            screen = pygame.display.get_surface()
            if 0 not in screen.get_size():               # окно свёрнуто: не рисуем
                self._update_background(dt, screen)
                self.scene.draw(screen)
                pygame.display.flip()

            self._apply_pending()