"""inputs — клавиши, привязки, снимок ввода и владелец мыши.
Снаружи: from inputs import InputHandler, Action, MouseOwner, COMBAT_HOLD"""
from .keymap import Action, MouseOwner, COMBAT_HOLD
from .handler import InputHandler

__all__ = ["Action", "MouseOwner", "COMBAT_HOLD", "InputHandler"]