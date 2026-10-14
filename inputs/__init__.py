"""inputs — клавиши, привязки, снимок ввода и владелец мыши.
Снаружи: from inputs import InputHandler, Action, MouseOwner, key_label"""
from .keymap import Action, MouseOwner, key_label, AMMO_HOTKEYS
from .handler import InputHandler

__all__ = ["Action", "MouseOwner", "key_label", "AMMO_HOTKEYS", "InputHandler"]