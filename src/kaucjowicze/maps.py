"""Map builders.

`build_test_map` is a placeholder with rectangular dormitories; it will be replaced
by a layout traced from the real AGH Student Campus map.
"""

from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid


def build_test_map(config: SimulationConfig) -> Grid:
    """Rows of rectangular dormitories with a single base in the middle."""
    grid = Grid(config.width, config.height)

    dorm_w, dorm_h = 8, 5
    gap_x, gap_y = 6, 6
    margin = 4
    for y in range(margin, config.height - dorm_h - margin + 1, dorm_h + gap_y):
        for x in range(margin, config.width - dorm_w - margin + 1, dorm_w + gap_x):
            grid.add_obstacle(x, y, dorm_w, dorm_h)

    center = (config.width // 2, config.height // 2)
    grid.add_base(_nearest_free(grid, center))
    return grid


def _nearest_free(grid: Grid, pos: tuple[int, int]) -> tuple[int, int]:
    """Closest free cell to `pos` (searching outward in square rings)."""
    x0, y0 = pos
    for r in range(max(grid.width, grid.height)):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                candidate = (x0 + dx, y0 + dy)
                if grid.is_free(candidate):
                    return candidate
    raise ValueError("Grid has no free cells")
