"""game/app.py — окно, главный цикл и смена сцен. Логики игры здесь нет."""
import pygame

from .scenes import MenuScene, PlayScene

class App:
    MAX_DT = 0.05   # защита от «телепорта» при подвисании окна

    def __init__(self, seed=None):
        pygame.init()
        pygame.display.set_mode((1000, 700), pygame.RESIZABLE)
        pygame.display.set_caption("Top-Down Танк (бесконечный мир)")
        self.clock = pygame.time.Clock()
        self.seed = seed                 # None: у каждой новой игры свой случайный мир

        self.running = True
        self.scene = None
        self._next = None                # функция, создающая следующую сцену (применяется в конце кадра)

        self.show_menu()
        self._apply_pending()

    # ---------- смена сцен (их передают сценам как колбэки) ----------
    def show_menu(self):
        self._next = lambda: MenuScene(on_play=self.start_game, on_quit=self.quit)

    def start_game(self):
        self._next = lambda: PlayScene(self.seed, self.clock,
                                       on_menu=self.show_menu, on_quit=self.quit)

    def quit(self):
        self.running = False

    def _apply_pending(self):
        """Сцену подменяем только между кадрами, а не посреди её собственного update."""
        if self._next is not None:
            factory, self._next = self._next, None
            self.scene = factory()

    # ---------- цикл ----------
    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, self.MAX_DT)
            self.scene.update(dt)

            screen = pygame.display.get_surface()
            if 0 not in screen.get_size():               # окно свёрнуто: не рисуем
                self.scene.draw(screen)
                pygame.display.flip()

            self._apply_pending()