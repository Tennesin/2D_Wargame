import sys
import pygame

from game import Game

if __name__ == "__main__":
    app = Game(seed=12345)
    app.run()
    pygame.quit()
    sys.exit()