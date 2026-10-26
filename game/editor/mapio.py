"""game/editor/mapio.py — перенос стен между MapData и WallManager (общий для редактора и партии)."""
from structures import Wall, WALL_PARAMS
from world import WallData

def load_walls(map_data, manager):
    """Стены из карты в менеджер. Значения подрезаем под границы ползунков."""
    P = WALL_PARAMS
    for w in map_data.walls:
        manager.add(Wall(w.x, w.y, P["wall_hp"].fit(w.hp), P["wall_width_m"].fit(w.width_m),
                         P["wall_length_m"].fit(w.length_m), w.angle))

def collect_walls(manager):
    """Стены менеджера в список WallData для записи в карту."""
    return [WallData(w.x, w.y, w.max_hp, w.width_m, w.length_m, w.angle) for w in manager.items]