"""scenes — сцены приложения: меню, конструктор и игра.
Снаружи: from .scenes import MenuScene, ConstructorScene, PlayScene"""
from .base import Scene
from .menu import MenuScene
from .constructor import ConstructorScene
from .play import PlayScene

__all__ = ["Scene", "MenuScene", "ConstructorScene", "PlayScene"]