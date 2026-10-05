"""input_handler.py — единственное место, которое читает клавиатуру и мышь.
В начале кадра process_events() делает «снимок» ввода; остальной код берёт данные только из него."""
import pygame

from common import VehicleCommand
from controls import (
    Action, HELD_KEYMAP, KEY_TO_PRESS,
    ZOOM_MODIFIER, ZOOM_IN_KEY, ZOOM_OUT_KEY, KEYS_BLOCKED_BY_ZOOM_MODIFIER,
)

ZOOM_KEY_DELAY = 0.35     # пауза перед автоповтором при удержании зума с клавиатуры, с
ZOOM_KEY_REPEAT = 0.08    # интервал автоповтора, с


class InputHandler:
    def __init__(self, ui_layers=()):
        self.ui_layers = list(ui_layers)   # слои интерфейса сверху вниз: у каждого handle_event и captures_mouse
        self.quit_requested = False

        # Игровые флаги, которым здесь не место; уедут в Game на этапе 3
        self.show_debug = False
        self.turret_follow = True          # башня следит за мышью (переключается действием LOCK_TURRET)

        self.zoom_steps = 0                # накопленные шаги зума (колёсико + клавиши), забирает Game
        self._zoom_dir = 0
        self._zoom_timer = 0.0
        self.world_clicks = []             # [(кнопка, (x, y) на экране)] — клики, которые не забрал интерфейс

        # ----- снимок кадра (обновляется в process_events) -----
        self.pressed = set()               # действия, нажатые именно в этом кадре
        self.held = set()                  # действия, удерживаемые сейчас
        self.mouse_pos = (0, 0)
        self.mouse_buttons = (False, False, False)   # (ЛКМ, СКМ, ПКМ) на момент снимка
        self.shift = False
        self._keys = pygame.key.get_pressed()

    # ==========================================
    # СНИМОК КАДРА
    # ==========================================
    def process_events(self):
        """События окна, затем снимок состояния. Вызывать один раз в начале кадра."""
        self.pressed = set()
        for event in pygame.event.get():
            if any(layer.handle_event(event) for layer in self.ui_layers):
                continue                  # событие забрал интерфейс
            if event.type == pygame.QUIT:
                self.quit_requested = True
            elif event.type == pygame.KEYDOWN:
                action = KEY_TO_PRESS.get(event.key)
                if action is not None:
                    self.pressed.add(action)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button in (1, 3):
                    self.world_clicks.append((event.button, event.pos))
            elif event.type == pygame.MOUSEWHEEL:
                self.zoom_steps += event.y        # вверх — приблизить, вниз — отдалить

        self._sample_state()

        # временно: эти два переключателя пока живут здесь (этап 3 перенесёт их в Game)
        if Action.TOGGLE_DEBUG in self.pressed:
            self.show_debug = not self.show_debug
        if Action.LOCK_TURRET in self.pressed:
            self.turret_follow = not self.turret_follow

    def _sample_state(self):
        """Единственное место во всей игре, где опрашиваются клавиатура и мышь."""
        self._keys = pygame.key.get_pressed()
        self.mouse_pos = pygame.mouse.get_pos()
        self.mouse_buttons = pygame.mouse.get_pressed()
        self.shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

        zoom_mod = bool(self._keys[ZOOM_MODIFIER])
        self.held = set()
        for action, keys in HELD_KEYMAP.items():
            for key in keys:
                if zoom_mod and key in KEYS_BLOCKED_BY_ZOOM_MODIFIER:
                    continue                      # стрелка вверх/вниз с Ctrl — это зум, а не газ
                if self._keys[key]:
                    self.held.add(action)
                    break

    def was_pressed(self, action):
        """Нажато ли действие в этом кадре (разово)."""
        return action in self.pressed

    # ==========================================
    # ИНТЕРФЕЙС И КЛИКИ
    # ==========================================
    def ui_captures_mouse(self):
        return any(layer.captures_mouse() for layer in self.ui_layers)

    def pop_world_clicks(self):
        clicks, self.world_clicks = self.world_clicks, []
        return clicks

    # ==========================================
    # ЗУМ
    # ==========================================
    def update_zoom_keys(self, dt):
        """Ctrl + Up/Down: шаг сразу при нажатии, затем автоповтор при удержании."""
        direction = 0
        if self._keys[ZOOM_MODIFIER]:
            direction = int(bool(self._keys[ZOOM_IN_KEY])) - int(bool(self._keys[ZOOM_OUT_KEY]))

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

    # ==========================================
    # КОМАНДА МАШИНЕ
    # ==========================================
    def read_command(self, camera, active=True) -> VehicleCommand:
        """Снимок ввода -> команда для машины. active=False: машиной не управляем (например, режим стройки)."""
        if not active:
            return VehicleCommand()

        steer = float(Action.RIGHT in self.held) - float(Action.LEFT in self.held)
        throttle = float(Action.FORWARD in self.held) - float(Action.BACKWARD in self.held)

        ui_busy = self.ui_captures_mouse()

        aim_point = None
        if self.turret_follow and not ui_busy:
            mx, my = self.mouse_pos
            aim_point = camera.screen_to_world(mx, my)   # экран -> мир

        fire = bool(self.mouse_buttons[0]) and not ui_busy

        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim_point, fire=fire)