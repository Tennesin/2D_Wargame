"""content/guide — страницы инструкции. Единственное место, где инструкция «знакомится»
с клавишами, снарядами и техникой. Клавиши берутся из inputs.key_label, числа из констант,
поэтому текст не устаревает при смене баланса или привязок.
Страница = функция build() без аргументов, возвращающая список блоков (см. PAGES внизу)."""
from .page_controls import build as _controls
from .page_ammo import build as _ammo
from .page_hits import build as _hits
from .page_vehicles import build as _vehicles
from .page_enemies import build as _enemies

# (подпись вкладки, функция-сборщик). Чтобы добавить страницу, создайте файл page_*.py и допишите строку.
PAGES = [
    ("Управление", _controls),
    ("Снаряды", _ammo),
    ("Попадания", _hits),
    ("Техника", _vehicles),
    ("Враги", _enemies),
]

def build_page(index):
    """Свежий список блоков страницы с номером index."""
    return PAGES[index][1]()