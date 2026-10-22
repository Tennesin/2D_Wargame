"""game/match/modes.py — режимы игры (езда / стройка / правка стены) и боевое состояние.
Единственное место, где режим меняется. О панелях и кнопках интерфейса не знает:
о смене режима сообщает через on_changed, интерфейс подстраивается сам."""
from enum import Enum, auto

from inputs import Action, MouseOwner
from ..config import COMBAT_HOLD

class Mode(Enum):
    DRIVE = auto()       # езда и стрельба
    BUILD = auto()       # расстановка стен: танк не управляется
    WALL_EDIT = auto()   # выбрана стена: открыта её панель, можно вращать

class Modes:
    def __init__(self, input_handler, walls):
        self.input = input_handler
        self.walls = walls

        self.mode = Mode.DRIVE           # единственный источник правды о режиме
        self.combat = False              # боевое состояние (Alt): огонь по ЛКМ и красная линия прицела
        self.turret_follow = True        # башня следит за мышью (Q)
        self.on_exit = None              # колбэк «выйти из партии в меню»
        self.on_changed = None           # колбэк (mode, wall): режим сменился; wall задан только в WALL_EDIT

    # ---------- смена состояния ----------
    def set_mode(self, mode, wall=None):
        """wall нужен только для WALL_EDIT."""
        if mode == Mode.WALL_EDIT and wall is None:
            mode = Mode.DRIVE
        self.mode = mode
        self.input.release_mouse(MouseOwner.ROTATE)
        if mode == Mode.BUILD:
            self.set_combat(False)                       # стройка и боевое состояние несовместимы

        self.walls.selected = wall if mode == Mode.WALL_EDIT else None
        if self.on_changed is not None:
            self.on_changed(mode, self.walls.selected)

    def set_combat(self, on):
        """В режиме стройки включить нельзя. При выключении стрельба обрывается."""
        if on and self.mode == Mode.BUILD:
            return
        self.combat = on
        if not on:
            self.input.release_mouse(MouseOwner.FIRE)

    def toggle_build(self):
        self.set_mode(Mode.DRIVE if self.mode == Mode.BUILD else Mode.BUILD)

    def handle_escape(self):
        """Esc закрывает по одному слою: стройка или стена, затем боевое состояние,
        а когда закрывать больше нечего, выход в меню."""
        if self.mode != Mode.DRIVE:
            self.set_mode(Mode.DRIVE)
        elif self.combat:
            self.set_combat(False)
        elif self.on_exit is not None:
            self.on_exit()

    # ---------- клавиши ----------
    def handle_hotkeys(self):
        inp = self.input
        if inp.was_pressed(Action.LOCK_TURRET):
            self.turret_follow = not self.turret_follow
        if inp.was_pressed(Action.TOGGLE_BUILD):
            self.toggle_build()

        if COMBAT_HOLD:
            self.set_combat(Action.COMBAT in inp.held)
        elif inp.was_pressed(Action.COMBAT):
            self.set_combat(not self.combat)

        if inp.was_pressed(Action.CANCEL):
            self.handle_escape()