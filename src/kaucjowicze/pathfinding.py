"""Grid search helpers: distance map to the nearest base and local search for visible cans.

Movement uses the 8-neighbourhood; every move (straight or diagonal) costs one step.
"""

from collections import deque

import numpy as np

from kaucjowicze.grid import Grid, Position

# Orthogonal moves first: among equally short paths, searches prefer straight lines.
NEIGHBOURS: tuple[Position, ...] = (
    (0, -1),
    (-1, 0),
    (1, 0),
    (0, 1),
    (-1, -1),
    (1, -1),
    (-1, 1),
    (1, 1),
)

UNREACHABLE = -1


def free_neighbours(grid: Grid, pos: Position) -> list[Position]:
    """Free cells adjacent to `pos` (8-neighbourhood), in `NEIGHBOURS` order."""
    x, y = pos
    return [(x + dx, y + dy) for dx, dy in NEIGHBOURS if grid.is_free((x + dx, y + dy))]


def distance_map(grid: Grid) -> np.ndarray:
    """Steps from every cell to the nearest base (multi-source BFS).

    Returns an int32 array indexed [y, x]; obstacles and unreachable cells are `UNREACHABLE`.
    """
    dist = np.full((grid.height, grid.width), UNREACHABLE, dtype=np.int32)
    queue: deque[Position] = deque()
    for base in grid.bases:
        if dist[base[1], base[0]] == UNREACHABLE:
            dist[base[1], base[0]] = 0
            queue.append(base)

    while queue:
        pos = queue.popleft()
        d = dist[pos[1], pos[0]] + 1
        for nx, ny in free_neighbours(grid, pos):
            if dist[ny, nx] == UNREACHABLE:
                dist[ny, nx] = d
                queue.append((nx, ny))
    return dist


def step_towards_base(grid: Grid, dist: np.ndarray, pos: Position) -> Position:
    """Neighbour one step closer to a base; `pos` if already at a base or unreachable."""
    best = pos
    best_dist = dist[pos[1], pos[0]]
    if best_dist <= 0:
        return pos
    for nx, ny in free_neighbours(grid, pos):
        d = dist[ny, nx]
        if d != UNREACHABLE and d < best_dist:
            best, best_dist = (nx, ny), d
    return best


def _view_window(grid: Grid, pos: Position, radius: int) -> np.ndarray:
    x, y = pos
    return grid.cans[max(y - radius, 0) : y + radius + 1, max(x - radius, 0) : x + radius + 1]


def _within(center: Position, pos: Position, radius: int) -> bool:
    return max(abs(pos[0] - center[0]), abs(pos[1] - center[1])) <= radius


def visible_cans(grid: Grid, pos: Position, radius: int) -> int:
    """Number of cans within Chebyshev distance `radius` of `pos`."""
    return int(_view_window(grid, pos, radius).sum())


def first_step_to_nearest_can(grid: Grid, pos: Position, radius: int) -> Position | None:
    """First move towards the nearest can the agent can see.

    The agent sees cells within Chebyshev distance `radius`; paths may not leave that window,
    so cans hidden behind a wall are not seen. Returns `pos` when standing on a can and `None`
    when no can is visible.
    """
    x, y = pos
    if grid.cans[y, x] > 0:
        return pos
    if not _view_window(grid, pos, radius).any():
        return None  # fast path: nothing in sight, skip the search

    first_step: dict[Position, Position] = {}
    queue: deque[Position] = deque()
    for nb in free_neighbours(grid, pos):
        if _within(pos, nb, radius):
            first_step[nb] = nb
            queue.append(nb)

    while queue:
        cell = queue.popleft()
        if grid.cans[cell[1], cell[0]] > 0:
            return first_step[cell]
        for nb in free_neighbours(grid, cell):
            if nb != pos and nb not in first_step and _within(pos, nb, radius):
                first_step[nb] = first_step[cell]
                queue.append(nb)
    return None
