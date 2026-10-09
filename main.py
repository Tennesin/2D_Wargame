import sys
import pygame

from game import App

if __name__ == "__main__":
    app = App(seed=12345)
    app.run()
    pygame.quit()
    sys.exit()