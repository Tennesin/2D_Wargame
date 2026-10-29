import sys
import pygame

from game import App

if __name__ == "__main__":
    app = App()
    app.run()
    pygame.quit()
    sys.exit()

# pyinstaller --onedir --noconsole --name "2D Wargame" main.py