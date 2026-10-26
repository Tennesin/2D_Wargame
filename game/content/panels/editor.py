"""game/content/panels/editor.py — панели редактора карт: по одной на инструмент, у каждой переключатель
инструментов и блок сведений о карте."""
from inputs import Action, key_label
from structures import ROTATE_SNAP_DEG
from ui import Panel, SectionHeader, StatsBlock, InfoText, ChoiceRow
from .kinds import PanelMode
from .wall import wall_items
from .rock import rock_items
from .land import land_items

STAT_NAME = "Название"
STAT_SIZE = "Размер"
STAT_ROCKS = "Камней"
STAT_WALLS = "Стен"
STAT_FILE = "Файл"

EDITOR_TOOLS = (("wall", "Стена"), ("rock", "Камень"), ("land", "Ландшафт"))
TOOL_MODE = {"wall": PanelMode.MAP_WALL, "rock": PanelMode.MAP_ROCK, "land": PanelMode.MAP_LAND}

def _hint(tool):
    delete = key_label(Action.DELETE_WALL)
    if tool == "wall":
        return ("ЛКМ по пустому месту ставит стену с параметрами ниже. Клик по стене выбирает её: "
                "ползунки тогда меняют именно её. Белая точка в центре поворачивает стену "
                f"(с Shift шаг {ROTATE_SNAP_DEG:.0f}°). {delete} удаляет выбранную, "
                "Esc или ПКМ снимают выбор.")
    if tool == "rock":
        return ("ЛКМ по пустому месту ставит камень; форма у курсора именно та, что будет поставлена. "
                "Стабильность: чем меньше, тем кривее и вытянутее камень. Сглаживание: от грубых граней "
                f"до мягкого контура. Клик по камню (ЛКМ или ПКМ) выбирает его, {delete} или кнопка удаляют. "
                f"{delete} без выбора удаляет камень под курсором. Esc или ПКМ по пустому месту снимают выбор.")
    return ("Зажмите ЛКМ и ведите мышью, чтобы красить. Равнина стирает любое покрытие. "
            "«Углубления» работают для водоёма: за один мазок каждая клетка воды становится на ступень "
            "глубже (мелководье, вода, глубокая вода). Рядом с центром карты, под камнями и стенами "
            "глубокая вода не рисуется.")

def _build(tool, label):
    items = [
        SectionHeader("Инструмент"),
        ChoiceRow("tool", "Выбор инструмента", list(EDITOR_TOOLS), tool),
        InfoText(_hint(tool)),
    ]
    if tool == "wall":
        items += wall_items()
    elif tool == "rock":
        items += rock_items()
    else:
        items += land_items()
    items += [
        SectionHeader("Карта"),
        StatsBlock([STAT_NAME, STAT_SIZE, STAT_ROCKS, STAT_WALLS, STAT_FILE]),
    ]
    return Panel(f"Редактор: {label}", items)

def build_editor_panels():
    """Словарь {PanelMode: Panel} для SidePanel редактора."""
    return {TOOL_MODE[key]: _build(key, label) for key, label in EDITOR_TOOLS}