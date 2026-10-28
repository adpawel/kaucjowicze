"""Can placement (static scenario): Gaussian clusters plus uniform background noise."""

import numpy as np

from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid


def scatter_cans(grid: Grid, config: SimulationConfig, rng: np.random.Generator) -> None:
    """Place clustered and background cans on free cells of the grid."""
    free = grid.free_cells()
    if len(free) == 0:
        raise ValueError("Grid has no free cells to place cans on")

    centers = free[rng.choice(len(free), size=config.n_clusters, replace=True)]
    for cx, cy in centers:
        _place_cluster(grid, (int(cx), int(cy)), config, rng)

    for idx in rng.choice(len(free), size=config.n_background_cans, replace=True):
        x, y = free[idx]
        grid.add_can((int(x), int(y)))


def _place_cluster(
    grid: Grid,
    center: tuple[int, int],
    config: SimulationConfig,
    rng: np.random.Generator,
) -> None:
    placed = 0
    attempts = 0
    max_attempts = config.cans_per_cluster * 20
    while placed < config.cans_per_cluster and attempts < max_attempts:
        attempts += 1
        dx, dy = rng.normal(0.0, config.cluster_spread, size=2)
        pos = (int(round(center[0] + dx)), int(round(center[1] + dy)))
        if grid.is_free(pos):
            grid.add_can(pos)
            placed += 1
    # Fallback for clusters squeezed between obstacles: put the rest in the centre
    if placed < config.cans_per_cluster:
        grid.add_can(center, config.cans_per_cluster - placed)
