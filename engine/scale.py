"""engine/scale.py — масштаб мира и его границы."""
PX_PER_M = 100.0   # МАСШТАБ МИРА: 100 px = 1 метр

WORLD_MIN_M = 250.0        # пределы ползунков «Размер карты», м
WORLD_MAX_M = 1250.0
WORLD_DEFAULT_M = 500.0    # размер по умолчанию (у ползунков в новой игре)
CAMERA_MARGIN_M = 100.0    # насколько центр камеры может выйти за край мира, м

class WorldBounds:
    """Границы мира: прямоугольник с центром в (0, 0). Один общий экземпляр WORLD на всё приложение.
    Размер задаётся ОДИН раз перед началом партии (PlayScene) и в ходе партии не меняется.
    Читать поля нужно в момент использования (WORLD.half_w_px), а не копировать в константы при импорте."""

    def __init__(self):
        self.set_size(WORLD_DEFAULT_M, WORLD_DEFAULT_M)

    def set_size(self, width_m, height_m):
        """width_m — размер по X, height_m — по Y (в сцене это «ширина» и «длина»)."""
        self.width_m = float(width_m)
        self.height_m = float(height_m)
        self.half_w_px = self.width_m * PX_PER_M / 2.0     # мир: x от -half_w_px до +half_w_px
        self.half_h_px = self.height_m * PX_PER_M / 2.0    # и y от -half_h_px до +half_h_px
        self.cam_w_px = self.half_w_px + CAMERA_MARGIN_M * PX_PER_M   # предел центра камеры
        self.cam_h_px = self.half_h_px + CAMERA_MARGIN_M * PX_PER_M

WORLD = WorldBounds()