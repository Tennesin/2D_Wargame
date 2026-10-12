"""inputs — клавиши, привязки, снимок ввода и владелец мыши.
Снаружи: from inputs import InputHandler, Action, MouseOwner, COMBAT_HOLD"""
from .keymap import Action, MouseOwner
from .handler import InputHandler

__all__ = ["Action", "MouseOwner", "InputHandler"]