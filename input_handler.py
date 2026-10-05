"""input_handler.py — единственное место, которое читает клавиатуру и мышь.
В начале кадра process_events() делает «снимок» ввода; остальной код берёт данные только из него.
Здесь же живёт «владелец мыши»: нажатая кнопка принадлежит одному владельцу до её отпускания."""
import pygame

from common import VehicleCommand
from controls import Action, MouseOwner, HELD_KEYMAP, KEY_TO_PRESS

ZOOM_KEY_DELAY = 0.35     # пауза перед автоповтором при удержании зума с клавиатуры, с
ZOOM_KEY_REPEAT = 0.08    # интервал автоповтора, с


class InputHandler:
    def __init__(self, ui_layers=()):
        # слои интерфейса сверху вниз: у каждого handle_event(event), covers(pos), cancel_drag()
        self.ui_layers = list(ui_layers)
        self.quit_requested = False

        self.zoom_steps = 0                # накопленные шаги зума (колёсико + клавиши), забирает Game
        self._zoom_dir = 0
        self._zoom_timer = 0.0
        self.world_clicks = []             # [(кнопка, (x, y))] — нажатия, которые не забрал интерфейс

        # ----- владелец мыши -----
        self.mouse_owner = None            # None или MouseOwner
        self._owner_button = 0             # какая кнопка (1..3) удерживает владение

        # ----- снимок кадра (обновляется в process_events) -----
        self.pressed = set()               # действия, нажатые именно в этом кадре
        self.held = set()                  # действия, удерживаемые сейчас
        self.mouse_pos = (0, 0)
        self.mouse_buttons = (False, False, False)   # (ЛКМ, СКМ, ПКМ) на момент снимка
        self.mouse_over_ui = False         # лежит ли курсор на интерфейсе
        self.shift = False

    # ==========================================
    # ВЛАДЕЛЕЦ МЫШИ
    # ==========================================
    def grab_mouse(self, owner, button):
        """Закрепить мышь за owner до отпускания кнопки button. Занятую мышь не перехватывает.
        Возвращает True, если получилось."""
        if self.mouse_owner is not None:
            return False
        self.mouse_owner = owner
        self._owner_button = button
        return True

    def release_mouse(self, owner=None):
        """Отпустить мышь. Если owner указан, то только когда мышь принадлежит именно ему."""
        if self.mouse_owner is None:
            return
        if owner is not None and self.mouse_owner != owner:
            return
        if self.mouse_owner == MouseOwner.UI:
            for layer in self.ui_layers:
                layer.cancel_drag()        # на случай, если «отпускание» до интерфейса не дошло
        self.mouse_owner = None
        self._owner_button = 0

    @property
    def pointer_in_world(self):
        """Курсор «работает на мир»: не над интерфейсом и не занят им или вращением стены.
        Удержание стрельбы (FIRE) прицеливанию не мешает."""
        return (not self.mouse_over_ui) and self.mouse_owner in (None, MouseOwner.FIRE)

    # ==========================================
    # СНИМОК КАДРА
    # ==========================================
    def process_events(self):
        """События окна, затем снимок состояния. Вызывать один раз в начале кадра."""
        self.pressed = set()
        for event in pygame.event.get():
            consumed = any(layer.handle_event(event) for layer in self.ui_layers)

            # владение мышью: берём, если нажатие забрал интерфейс; отдаём при отпускании своей кнопки
            if event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 2, 3):
                if consumed:
                    self.grab_mouse(MouseOwner.UI, event.button)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == self._owner_button:
                    self.release_mouse()

            if consumed:
                continue                  # событие забрал интерфейс
            if event.type == pygame.QUIT:
                self.quit_requested = True
            elif event.type == pygame.KEYDOWN:
                action = KEY_TO_PRESS.get(event.key)
                if action is not None:
                    self.pressed.add(action)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # пока кнопка занята (стрельба, вращение, ползунок), другие клики мир не получает
                if event.button in (1, 3) and self.mouse_owner is None:
                    self.world_clicks.append((event.button, event.pos))
            elif event.type == pygame.MOUSEWHEEL:
                self.zoom_steps += event.y        # вверх — приблизить, вниз — отдалить

        self._sample_state()

    def _sample_state(self):
        """Единственное место во всей игре, где опрашиваются клавиатура и мышь."""
        keys = pygame.key.get_pressed()
        self.mouse_pos = pygame.mouse.get_pos()
        self.mouse_buttons = pygame.mouse.get_pressed()
        self.shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

        # страховка: владеющая кнопка уже отпущена, а событие отпускания потерялось
        if self.mouse_owner is not None and not self.mouse_buttons[self._owner_button - 1]:
            self.release_mouse()

        self.mouse_over_ui = any(layer.covers(self.mouse_pos) for layer in self.ui_layers)

        self.held = {action for action, codes in HELD_KEYMAP.items()
                     if any(keys[code] for code in codes)}

    def was_pressed(self, action):
        """Нажато ли действие в этом кадре (разово)."""
        return action in self.pressed

    # ==========================================
    # КЛИКИ ПО МИРУ
    # ==========================================
    def pop_world_clicks(self):
        clicks, self.world_clicks = self.world_clicks, []
        return clicks

    # ==========================================
    # ЗУМ
    # ==========================================
    def update_zoom_keys(self, dt):
        """Клавиши зума: шаг сразу при нажатии, затем автоповтор при удержании."""
        direction = int(Action.ZOOM_IN in self.held) - int(Action.ZOOM_OUT in self.held)

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
    def read_command(self, camera, *, active=True, follow_mouse=True, combat=False) -> VehicleCommand:
        """Снимок ввода -> команда для машины.
        active=False: машиной не управляем (режим стройки).
        follow_mouse: следит ли башня за курсором. combat: боевое состояние (без него огня нет)."""
        if not active:
            return VehicleCommand()

        steer = float(Action.RIGHT in self.held) - float(Action.LEFT in self.held)
        throttle = float(Action.FORWARD in self.held) - float(Action.BACKWARD in self.held)

        aim_point = None
        if follow_mouse and self.pointer_in_world:
            aim_point = camera.screen_to_world(*self.mouse_pos)   # экран -> мир

        fire = combat and self.mouse_owner == MouseOwner.FIRE

        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim_point, fire=fire)