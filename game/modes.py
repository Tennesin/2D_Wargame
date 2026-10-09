"""game/modes.py — режимы игры (езда / стройка / правка стены) и боевое состояние.
Единственное место, где режим меняется; всё, что от него зависит (выбранная стена, кнопка,
панель, захват мыши), приводится в порядок в set_mode."""
from enum import Enum, auto

from inputs import Action, MouseOwner, COMBAT_HOLD
from .panels import PanelMode, wall_values

class Mode(Enum):
    DRIVE = auto()       # езда и стрельба
    BUILD = auto()       # расстановка стен: танк не управляется
    WALL_EDIT = auto()   # выбрана стена: открыта её панель, можно вращать

class Modes:
    def __init__(self, input_handler, walls, toolbar, ui):
        self.input = input_handler
        self.walls = walls
        self.toolbar = toolbar
        self.ui = ui

        self.mode = Mode.DRIVE           # единственный источник правды о режиме
        self.combat = False              # боевое состояние (Alt): огонь по ЛКМ и красная линия прицела
        self.turret_follow = True        # башня следит за мышью (Q)

        toolbar.on_create_wall = self.toggle_build

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
        self.toolbar.set_active(mode == Mode.BUILD)
        if mode == Mode.WALL_EDIT:
            self.ui.show(PanelMode.WALL, wall_values(wall), auto_open=True)
        else:
            self.ui.show(PanelMode.TANK)

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
        """Esc закрывает по одному слою: стройка или стена, затем боевое состояние."""
        if self.mode != Mode.DRIVE:
            self.set_mode(Mode.DRIVE)
        elif self.combat:
            self.set_combat(False)

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