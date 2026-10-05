"""input_handler.py — превращает клавиатуру и мышь в VehicleCommand."""
import pygame

from common import VehicleCommand

ZOOM_KEY_DELAY = 0.35     # пауза перед автоповтором при удержании LCtrl + Up/Down, с
ZOOM_KEY_REPEAT = 0.08    # интервал автоповтора, с

class InputHandler:
    def __init__(self, ui=None):
        self.ui = ui
        self.quit_requested = False
        self.show_debug = False
        self.turret_follow = True     # башня следит за мышью (переключается клавишей Q)
        self.zoom_steps = 0           # накопленные шаги зума (колёсико + клавиши), забирает Game
        self._zoom_dir = 0
        self._zoom_timer = 0.0

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
                elif event.key == pygame.K_q:
                    self.turret_follow = not self.turret_follow
            elif event.type == pygame.MOUSEWHEEL:
                self.zoom_steps += event.y        # вверх — приблизить, вниз — отдалить

    def update_zoom_keys(self, dt):
        """LCtrl + Up/Down: шаг сразу при нажатии, затем автоповтор при удержании."""
        keys = pygame.key.get_pressed()
        direction = 0
        if keys[pygame.K_LCTRL]:
            direction = int(bool(keys[pygame.K_UP])) - int(bool(keys[pygame.K_DOWN]))

        if direction == 0:
            self._zoom_dir = 0
            return
        if direction != self._zoom_dir:           # новое нажатие
            self._zoom_dir = direction
            self._zoom_timer = ZOOM_KEY_DELAY
            self.zoom_steps += direction
            return
        self._zoom_timer -= dt
        if self._zoom_timer <= 0.0:
            self._zoom_timer += ZOOM_KEY_REPEAT
            self.zoom_steps += direction

    def pop_zoom_steps(self):
        steps, self.zoom_steps = self.zoom_steps, 0
        return steps

    def read_command(self, camera) -> VehicleCommand:
        """Удерживаемые клавиши и мышь -> команда для машины."""
        keys = pygame.key.get_pressed()

        left = bool(keys[pygame.K_a] or keys[pygame.K_LEFT])
        right = bool(keys[pygame.K_d] or keys[pygame.K_RIGHT])
        ctrl = bool(keys[pygame.K_LCTRL])
        forward = bool(keys[pygame.K_w] or (keys[pygame.K_UP] and not ctrl))
        backward = bool(keys[pygame.K_s] or (keys[pygame.K_DOWN] and not ctrl))

        steer = float(right) - float(left)
        throttle = float(forward) - float(backward)

        aim_point = None
        ui_busy = self.ui is not None and self.ui.captures_mouse()

        aim_point = None
        if self.turret_follow and not ui_busy:
            mx, my = pygame.mouse.get_pos()
            aim_point = camera.screen_to_world(mx, my)   # экран -> мир

        fire = bool(pygame.mouse.get_pressed()[0]) and not ui_busy

        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim_point, fire=fire)