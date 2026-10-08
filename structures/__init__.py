"""structures — постройки. Сейчас только стена.
Снаружи: from structures import Wall, WallManager, WallRenderer, WALL_PARAMS, ..."""
from .wall import (WALL_PARAMS, PLACE_REPEAT,
                   ROTATE_HANDLE_HIT_PX, ROTATE_DEAD_ZONE_PX, ROTATE_SNAP_DEG,
                   Wall, WallManager, WallRenderer)

__all__ = ["WALL_PARAMS", "PLACE_REPEAT", "ROTATE_HANDLE_HIT_PX", "ROTATE_DEAD_ZONE_PX",
           "ROTATE_SNAP_DEG", "Wall", "WallManager", "WallRenderer"]