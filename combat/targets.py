"""combat/targets.py — набор целей для снарядов и прицела: объединяет источники
(WallManager, TerrainMap, Fleet...). Правил брони здесь нет, они в armor.py."""

class TargetSet:
    """Объединяет источники целей."""

    def __init__(self, *sources):
        self.sources = list(sources)

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Ближайшая цель на отрезке. ignore — ЦЕЛЬ, которую пропускаем (обычно сам стрелок).
        Он передаётся и источникам: иначе стрелок, чей корпус лежит в начале отрезка (t = 0),
        заслонил бы собой врага."""
        best = None
        for src in self.sources:
            res = src.raycast(x0, y0, x1, y1, ignore)
            if res is None or res[0] is ignore:
                continue
            if best is None or res[1] < best[1]:
                best = res
        return best

    def in_circle(self, x, y, r, ignore=None):
        """Все цели в круге: [(цель, расстояние), ...]. Источники без метода in_circle
        (карта препятствий: камни неразрушимы) пропускаются."""
        found = []
        for src in self.sources:
            fn = getattr(src, "in_circle", None)
            if fn is not None:
                found.extend(fn(x, y, r, ignore))
        return found