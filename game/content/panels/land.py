"""game/content/panels/land.py — элементы панели «Ландшафт» (редактор карт) и связка с LandTool."""
from engine import Param
from ui import SectionHeader, InfoText, ChoiceRow, make_param_row
from .kinds import PanelMode

LAND_PARAMS = {"land_radius_m": Param("Размер кисти", "м", 1, 30, 5, 1)}
LAND_BIOMES = [("plain", "Равнина"), ("mud", "Глина"), ("water", "Водоём")]
LAND_DEEPEN = [("off", "Выкл"), ("on", "Вкл")]

def land_items():
    return [
        SectionHeader("Кисть"),
        ChoiceRow("land_biome", "Покрытие", LAND_BIOMES, "plain"),
        make_param_row(LAND_PARAMS, "land_radius_m"),
        ChoiceRow("land_deepen", "Углубления", LAND_DEEPEN, "off", note="только водоём"),
    ]

class LandPanelLink:
    """Даёт инструменту значения панели и включает «Углубления» только при покрытии «Водоём»."""

    def __init__(self, ui, tool, mode=PanelMode.MAP_LAND):
        self.ui = ui
        self.tool = tool
        self.mode = mode
        tool.get_params = self.template
        self.on_params_change(self.template())

    def template(self):
        return self.ui.get_values(self.mode)

    def on_params_change(self, values):
        self.ui.set_enabled(self.mode, "land_deepen", values.get("land_biome") == "water")