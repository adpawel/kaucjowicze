"""Can placement: Gaussian clusters plus uniform background noise, and parties during a run."""

from dataclasses import dataclass

import numpy as np

from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid, Position


@dataclass(frozen=True)
class SpawnEvent:
    """A party: at the start of step `step` one can lands on each of `cells` (repeats allowed)."""

    id: int  # 1, 2, ...; 0 stands for the cans present from the start
    step: int
    center: Position
    cells: tuple[Position, ...]

    @property
    def cans(self) -> int:
        return len(self.cells)


def scatter_cans(grid: Grid, config: SimulationConfig, rng: np.random.Generator) -> None:
    """Place clustered and background cans on free cells of the grid."""
    free = grid.free_cells()
    if len(free) == 0:
        raise ValueError("Grid has no free cells to place cans on")

    candidates = _cluster_candidates(grid, config, free)
    centers = candidates[rng.choice(len(candidates), size=config.n_clusters, replace=True)]
    for cx, cy in centers:
        for pos in cluster_cells(grid, (int(cx), int(cy)), config.cans_per_cluster, config, rng):
            grid.add_can(pos)

    for idx in rng.choice(len(free), size=config.n_background_cans, replace=True):
        x, y = free[idx]
        grid.add_can((int(x), int(y)))


def _cluster_candidates(grid: Grid, config: SimulationConfig, free: np.ndarray) -> np.ndarray:
    """Free cells close to a dormitory, or all free cells on a map without dormitories."""
    if not grid.dormitories.any():
        return free
    distance = config.cluster_dorm_distance
    size = 2 * distance + 1
    windows = np.lib.stride_tricks.sliding_window_view(
        np.pad(grid.dormitories, distance), (size, size)
    )
    near = windows.any(axis=(2, 3))
    close = free[near[free[:, 1], free[:, 0]]]
    if len(close) == 0:
        raise ValueError(f"No free cell within {distance} cells of a dormitory")
    return close


def schedule_events(
    grid: Grid, config: SimulationConfig, rng: np.random.Generator
) -> list[SpawnEvent]:
    """Parties of a run, drawn up front so every variant gets the same ones for a seed.

    Centres follow the rule of the starting clusters. Only obstacles decide where a can may lie,
    so the cells do not depend on what the agents do. `rng` should be a stream of its own.
    """
    if not config.n_events:
        return []
    candidates = _cluster_candidates(grid, config, grid.free_cells())
    events = []
    for index in range(config.n_events):
        cx, cy = candidates[rng.integers(len(candidates))]
        center = (int(cx), int(cy))
        cells = cluster_cells(grid, center, config.cans_per_event, config, rng)
        step = config.event_start + index * config.event_interval
        events.append(SpawnEvent(index + 1, step, center, tuple(cells)))
    return events


def cluster_cells(
    grid: Grid,
    center: Position,
    count: int,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> list[Position]:
    """Cells of `count` cans spread around `center`; a cell appears once per can."""
    cells = []
    attempts = 0
    max_attempts = count * 20
    while len(cells) < count and attempts < max_attempts:
        attempts += 1
        dx, dy = rng.normal(0.0, config.cluster_spread, size=2)
        pos = (int(round(center[0] + dx)), int(round(center[1] + dy)))
        if grid.is_free(pos):
            cells.append(pos)
    # Fallback for clusters squeezed between obstacles: put the rest in the centre
    cells.extend([center] * (count - len(cells)))
    return cells
