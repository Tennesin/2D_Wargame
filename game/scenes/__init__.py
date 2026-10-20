"""scenes — сцены приложения."""
from .base import Scene
from .menu import MenuScene
from .constructor import ConstructorScene
from .play import PlayScene
from .settings import SettingsScene
from .instruction import InstructionScene

__all__ = ["Scene", "MenuScene", "ConstructorScene", "PlayScene", "SettingsScene", "InstructionScene"]