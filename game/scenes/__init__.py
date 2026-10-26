"""scenes — сцены приложения."""
from .base import Scene
from .menu import MenuScene
from .newgame import NewGameScene
from .constructor import ConstructorScene
from .play import PlayScene
from .settings import SettingsScene
from .instruction import InstructionScene
from .stats import StatsScene, ResultScene
from .map_list import MapListScene
from .new_map import NewMapScene
from .map_editor import MapEditorScene

__all__ = ["Scene", "MenuScene", "ConstructorScene", "PlayScene",
           "SettingsScene", "InstructionScene", "NewGameScene",
           "StatsScene", "ResultScene", "MapListScene", "NewMapScene", "MapEditorScene"]