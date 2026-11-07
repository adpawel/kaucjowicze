"""Map builders.

`build_test_map` gives rectangular dormitories. `load_mask` reads a map from a PNG with one pixel
per cell; the campus mask is generated from OpenStreetMap by `tools/build_campus_map.py`.
"""

from pathlib import Path

import numpy as np
from PIL import Image

from kaucjowicze.config import CAMPUS_MAP, SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.pathfinding import UNREACHABLE, distance_map

CAMPUS_MASK = Path(__file__).parent / "data" / "ms_agh_map.png"
CAMPUS_PHOTO = Path(__file__).parent / "data" / "ms_agh_photo.jpg"

FREE_COLOR = (255, 255, 255)
OBSTACLE_COLOR = (0, 0, 0)
DORMITORY_COLOR = (128, 128, 128)
BASE_COLOR = (0, 0, 255)


def build_map(config: SimulationConfig) -> Grid:
    """The map chosen in `config`."""
    if config.map_name == CAMPUS_MAP:
        return load_mask(CAMPUS_MASK)
    return build_test_map(config)


def map_photo(config: SimulationConfig) -> Path | None:
    """Aerial photo covering exactly the map, if the map has one. Only the window uses it."""
    return CAMPUS_PHOTO if config.map_name == CAMPUS_MAP else None


def load_mask(path: str | Path) -> Grid:
    """Read a map from a PNG: white is walkable, black an obstacle, grey a dormitory (an obstacle
    near which can clusters appear) and blue a base.

    The file can be edited by hand, so a stray color or an enclosed area is reported here. Cans
    placed in an enclosed area could never be collected.
    """
    with Image.open(path) as image:
        pixels = np.array(image.convert("RGB"))

    free = (pixels == FREE_COLOR).all(axis=2)
    dormitory = (pixels == DORMITORY_COLOR).all(axis=2)
    obstacle = (pixels == OBSTACLE_COLOR).all(axis=2) | dormitory
    base = (pixels == BASE_COLOR).all(axis=2)
    unknown = ~(free | obstacle | base)
    if unknown.any():
        y, x = (int(i[0]) for i in np.nonzero(unknown))
        color = tuple(int(c) for c in pixels[y, x])
        raise ValueError(f"Unknown color {color} at ({x}, {y}) in {path}")
    if not base.any():
        raise ValueError(f"No base in {path}")

    height, width = obstacle.shape
    grid = Grid(width, height)
    grid.obstacles = obstacle
    grid.dormitories = dormitory
    for y, x in zip(*np.nonzero(base), strict=True):
        grid.add_base((int(x), int(y)))

    enclosed = ~obstacle & (distance_map(grid) == UNREACHABLE)
    if enclosed.any():
        y, x = (int(i[0]) for i in np.nonzero(enclosed))
        raise ValueError(f"{int(enclosed.sum())} cells cannot reach a base, e.g. ({x}, {y})")
    return grid


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
