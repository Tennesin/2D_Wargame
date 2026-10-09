"""scenes — сцены приложения: меню и игра.
Снаружи: from .scenes import MenuScene, PlayScene"""
from .base import Scene
from .menu import MenuScene
from .play import PlayScene

__all__ = ["Scene", "MenuScene", "PlayScene"]