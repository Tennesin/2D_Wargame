"""input_handler.py — превращает клавиатуру и мышь в VehicleCommand."""
import pygame

from core import VehicleCommand


class InputHandler:
    def __init__(self, ui=None):
        self.ui = ui
        self.quit_requested = False
        self.show_debug = False

    def process_events(self):
        """События окна и разовые клавиши (выход, отладка)."""
        for event in pygame.event.get():
            if self.ui is not None and self.ui.handle_event(event):
                continue                  # событие забрал интерфейс
            if event.type == pygame.QUIT:
                self.quit_requested = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.quit_requested = True
                elif event.key == pygame.K_F3:
                    self.show_debug = not self.show_debug

    def read_command(self, camera) -> VehicleCommand:
        """Удерживаемые клавиши и мышь -> команда для машины."""
        keys = pygame.key.get_pressed()

        left = bool(keys[pygame.K_a] or keys[pygame.K_LEFT])
        right = bool(keys[pygame.K_d] or keys[pygame.K_RIGHT])
        forward = bool(keys[pygame.K_w] or keys[pygame.K_UP])
        backward = bool(keys[pygame.K_s] or keys[pygame.K_DOWN])

        steer = float(right) - float(left)
        throttle = float(forward) - float(backward)

        aim_point = None
        ui_busy = self.ui is not None and self.ui.captures_mouse()
        if pygame.mouse.get_pressed()[0] and not ui_busy:
            mx, my = pygame.mouse.get_pos()
            aim_point = camera.screen_to_world(mx, my)   # экран -> мир

        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim_point, fire=False)