"""tools/preview_background.py — просмотр фона: цифры 1-9 запускают события по порядку, Esc выход.
Запуск из корня проекта: python -m tools.preview_background"""
import pygame

from game.background import Backdrop
from game.background.events import EVENTS
from game.state.session import Session

def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    clock = pygame.time.Clock()
    backdrop = Backdrop(Session())
    keys = list(EVENTS)
    print("События:", ", ".join(f"{i + 1}={k}" for i, k in enumerate(keys)))
    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif pygame.K_1 <= e.key <= pygame.K_9 and e.key - pygame.K_1 < len(keys):
                    key = keys[e.key - pygame.K_1]
                    backdrop.play(key)
                    pygame.display.set_caption(key)
        screen = pygame.display.get_surface()
        backdrop.update(dt, screen.get_size())
        backdrop.draw(screen)
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()