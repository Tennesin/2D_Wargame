import sys
import pygame

from game import Game

if __name__ == "__main__":
    app = Game()
    app.run()
    pygame.quit()
    sys.exit()