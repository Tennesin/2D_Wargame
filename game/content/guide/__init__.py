"""content/guide — страницы инструкции."""
from .page_controls import build as _controls
from .page_game import build as _game
from .page_vehicles import build as _vehicles
from .page_ammo import build as _ammo
from .page_hits import build as _hits
from .page_enemies import build as _enemies
from .page_editor import build as _editor

PAGES = [
    ("Управление", _controls),
    ("Игра", _game),
    ("Техника", _vehicles),
    ("Снаряды", _ammo),
    ("Попадания", _hits),
    ("Враги", _enemies),
    ("Редактор карт", _editor),
]

def build_page(index):
    """Свежий список блоков страницы с номером index."""
    return PAGES[index][1]()