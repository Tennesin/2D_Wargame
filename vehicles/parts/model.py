"""vehicles/parts/model.py — деталь техники как данные: поверхность, слой, сама деталь и контекст рисования.
Правила: координаты в метрах поверхности (HULL: начало в центре корпуса, +x вправо, +y назад, перёд = -y).
Слой z лежит внутри одной из полос BAND_*: полоса соответствует точке в коде рендерера."""
from dataclasses import dataclass
from typing import Optional

SURFACE_HULL = "hull"
SURFACE_TURRET = "turret"
SURFACE_BARREL = "barrel"
SURFACES = (SURFACE_HULL, SURFACE_TURRET, SURFACE_BARREL)

ANCHOR_HULL = "hull"          # абсолютные метры корпуса (настоящие якоря появятся в этапе 2)

CAT_DECOR = "decor"           # только картинка
CAT_FUNCTIONAL = "functional" # влияет на игру (экраны корпуса, этап 5)

# полосы слоёв: (с, до) — детали с lo <= z < hi рисуются в своей точке рендерера
BAND_FENDER = (0, 20)         # после подкрылков, до бортовых экранов
BAND_DECK = (20, 40)          # после палубы и носа, до накладной брони
BAND_COVER = (40, 60)         # после лобовых экранов, до погона
BAND_TOP = (60, 100)          # после погона

@dataclass(frozen=True)
class Part:
    """Неизменяемая и хэшируемая деталь: список таких деталей годится как часть ключа кэша спрайта."""
    kind: str                       # ключ типа в PART_TYPES
    x: float = 0.0                  # положение (относительно якоря), м
    y: float = 0.0
    w: float = 0.0                  # размер; смысл зависит от типа (радиус, ширина, длина)
    h: float = 0.0
    angle: float = 0.0              # градусы, по часовой
    mirror: bool = False            # отражение по оси x детали
    variant: int = 0
    z: Optional[int] = None         # None: слой типа
    surface: str = SURFACE_HULL
    anchor: str = ANCHOR_HULL

@dataclass
class PartCtx:
    """Что нужно функциям рисования, кроме самой детали."""
    paint: Optional[tuple]          # цвет команды для подкраски (None у игрока)
    look: object                    # Look техники
    layout: object                  # HullLayout
    team: Optional[tuple] = None    # цвет команды (деталям башни и маски)