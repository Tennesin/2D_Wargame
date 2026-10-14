"""inputs — клавиши, привязки, снимок ввода и владелец мыши.
Снаружи: from inputs import InputHandler, Action, MouseOwner, key_label"""
from .keymap import Action, MouseOwner, key_label
from .handler import InputHandler

__all__ = ["Action", "MouseOwner", "key_label", "InputHandler"]