"""game/match/modes.py — боевое состояние (Alt) и слежение башни за мышью.
О панелях и кнопках интерфейса не знает."""
from inputs import Action, MouseOwner
from ..config import COMBAT_HOLD

class Modes:
    def __init__(self, input_handler):
        self.input = input_handler
        self.combat = False              # боевое состояние (Alt): огонь по ЛКМ и красная линия прицела
        self.turret_follow = True        # башня следит за мышью (Q)
        self.on_exit = None              # колбэк «выйти из партии в меню»

    def set_combat(self, on):
        """При выключении стрельба обрывается."""
        self.combat = on
        if not on:
            self.input.release_mouse(MouseOwner.FIRE)

    def handle_escape(self):
        """Esc: сначала выключает боевое состояние, а когда закрывать нечего, выход в меню."""
        if self.combat:
            self.set_combat(False)
        elif self.on_exit is not None:
            self.on_exit()

    def handle_hotkeys(self):
        inp = self.input
        if inp.was_pressed(Action.LOCK_TURRET):
            self.turret_follow = not self.turret_follow

        if COMBAT_HOLD:
            self.set_combat(Action.COMBAT in inp.held)
        elif inp.was_pressed(Action.COMBAT):
            self.set_combat(not self.combat)

        if inp.was_pressed(Action.CANCEL):
            self.handle_escape()