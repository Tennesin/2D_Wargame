import sys
import pygame

import tank_config
from game import Game

if __name__ == "__main__":
    tank_config.print_tank_specs()
    app = Game()
    app.run()
    pygame.quit()
    sys.exit()