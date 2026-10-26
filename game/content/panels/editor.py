"""game/content/panels/editor.py — панели редактора карт: по одной на инструмент, у каждой переключатель
инструментов и блок сведений о карте. Содержимое инструментов подключается на этапах 5, 7 и 8."""
from inputs import Action, key_label
from structures import ROTATE_SNAP_DEG
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow
from .kinds import PanelMode
from .wall import wall_items

STAT_NAME = "Название"
STAT_SIZE = "Размер"
STAT_ROCKS = "Камней"
STAT_WALLS = "Стен"
STAT_FILE = "Файл"

EDITOR_TOOLS = (("wall", "Стена"), ("rock", "Камень"), ("land", "Ландшафт"))
TOOL_MODE = {"wall": PanelMode.MAP_WALL, "rock": PanelMode.MAP_ROCK, "land": PanelMode.MAP_LAND}
TOOL_HINTS = {
    "rock": "Камень: размер, стабильность и сглаживание формы (подключается на этапе 7).",
    "land": "Ландшафт: кисть для равнины, глины и воды (подключается на этапе 8).",
}

def _hint(tool):
    if tool == "wall":
        return ("ЛКМ по пустому месту ставит стену с параметрами ниже. Клик по стене выбирает её: "
                "ползунки тогда меняют именно её. Белая точка в центре поворачивает стену "
                f"(с Shift шаг {ROTATE_SNAP_DEG:.0f}°). {key_label(Action.DELETE_WALL)} удаляет выбранную, "
                "Esc или ПКМ снимают выбор.")
    return TOOL_HINTS[tool]

def _build(tool, label):
    items = [
        SectionHeader("Инструмент"),
        ChoiceRow("tool", "Выбор инструмента", list(EDITOR_TOOLS), tool),
        InfoText(_hint(tool)),
    ]
    if tool == "wall":
        items += wall_items()
    items += [
        SectionHeader("Карта"),
        StatsBlock([STAT_NAME, STAT_SIZE, STAT_ROCKS, STAT_WALLS, STAT_FILE]),
    ]
    return Panel(f"Редактор: {label}", items)

def build_editor_panels():
    """Словарь {PanelMode: Panel} для SidePanel редактора."""
    return {TOOL_MODE[key]: _build(key, label) for key, label in EDITOR_TOOLS}