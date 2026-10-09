"""engine/scale.py — масштаб мира и его границы."""
PX_PER_M = 100.0   # МАСШТАБ МИРА: 100 px = 1 метр (все скорости и расстояния в метрах переводим через него)

WORLD_SIZE_M = 1500.0                              # сторона квадратного мира, м
WORLD_HALF_PX = WORLD_SIZE_M * PX_PER_M / 2.0      # мир занимает [-WORLD_HALF_PX; +WORLD_HALF_PX] по обеим осям
CAMERA_MARGIN_M = 100.0                            # насколько центр камеры может выйти за край мира, м
CAMERA_LIMIT_PX = WORLD_HALF_PX + CAMERA_MARGIN_M * PX_PER_M