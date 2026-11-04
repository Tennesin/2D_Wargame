import sys
import pygame

from game import App

if __name__ == "__main__":
    app = App()
    app.run()
    pygame.quit()
    sys.exit()

# build_env/scripts/activate
# pyinstaller --onedir --noconsole --noupx --clean --name "wargame2d" --icon assets/tank.ico --version-file version_info.txt main.py