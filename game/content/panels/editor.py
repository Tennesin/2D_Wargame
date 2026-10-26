"""game/content/panels/editor.py — панели редактора карт: по одной на инструмент, у каждой переключатель
инструментов и блок сведений о карте. Содержимое инструментов подключается на этапах 5, 7 и 8."""
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow
from .kinds import PanelMode

STAT_NAME = "Название"
STAT_SIZE = "Размер"
STAT_ROCKS = "Камней"
STAT_WALLS = "Стен"
STAT_FILE = "Файл"

EDITOR_TOOLS = (("wall", "Стена"), ("rock", "Камень"), ("land", "Ландшафт"))
TOOL_MODE = {"wall": PanelMode.MAP_WALL, "rock": PanelMode.MAP_ROCK, "land": PanelMode.MAP_LAND}
TOOL_HINTS = {
    "wall": "Стена: ЛКМ ставит и выбирает стены (подключается на этапе 5).",
    "rock": "Камень: размер, стабильность и сглаживание формы (подключается на этапе 7).",
    "land": "Ландшафт: кисть для равнины, глины и воды (подключается на этапе 8).",
}

def _build(tool, label):
    return Panel(f"Редактор: {label}", [
        SectionHeader("Инструмент"),
        ChoiceRow("tool", "Выбор инструмента", list(EDITOR_TOOLS), tool),
        InfoText(TOOL_HINTS[tool]),

        SectionHeader("Карта"),
        StatsBlock([STAT_NAME, STAT_SIZE, STAT_ROCKS, STAT_WALLS, STAT_FILE]),
    ])

def build_editor_panels():
    """Словарь {PanelMode: Panel} для SidePanel редактора."""
    return {TOOL_MODE[key]: _build(key, label) for key, label in EDITOR_TOOLS}