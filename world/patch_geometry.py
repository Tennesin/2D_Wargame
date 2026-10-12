"""world/patch_geometry.py — пересечение пятен местности (многоугольников)."""

def _segments_cross(a, b, c, d):
    """Пересекаются ли отрезки ab и cd."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return ((orient(a, b, c) > 0) != (orient(a, b, d) > 0)
            and (orient(c, d, a) > 0) != (orient(c, d, b) > 0))

def patches_overlap(p, q):
    """Пересекаются ли два пятна (точно, по многоугольникам; сначала дешёвая проверка по кругам)."""
    dx, dy = p.x - q.x, p.y - q.y
    lim = p.r_max + q.r_max
    if dx * dx + dy * dy > lim * lim:
        return False
    if any(q.contains(x, y) for x, y in p.pts):      # вершина одного внутри другого
        return True
    if any(p.contains(x, y) for x, y in q.pts):
        return True
    n, m = len(p.pts), len(q.pts)
    for i in range(n):                               # рёбра пересекаются без вершин внутри
        a, b = p.pts[i], p.pts[(i + 1) % n]
        for j in range(m):
            if _segments_cross(a, b, q.pts[j], q.pts[(j + 1) % m]):
                return True
    return False