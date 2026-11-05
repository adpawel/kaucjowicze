"""Building a ready-to-run simulation of a chosen variant."""

from dataclasses import replace

import numpy as np

from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_test_map
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import AcoPolicy, IndividualPolicy, RandomWalkPolicy
from kaucjowicze.rewards import INDIVIDUAL, SHARED
from kaucjowicze.simulation import Simulation

ALGORITHMS = ("random", "aco")


def build_simulation(
    algorithm: str,
    seed: int | None,
    reward: str | None = None,
    config: SimulationConfig | None = None,
) -> Simulation:
    """A fresh simulation; the same arguments and an integer seed give an identical run.

    `reward` picks the variant of ACO, by default the shared one. The random walk has none.
    `seed` replaces the seed in `config`. Cans are scattered before any policy draws a number,
    so all variants get the same map for the same seed.
    """
    config = replace(config or SimulationConfig(), seed=seed)
    rng = np.random.default_rng(config.seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    if algorithm == "random":
        if reward is not None:
            raise ValueError("The random walk does not use a reward")
        return Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)
    if algorithm == "aco":
        if reward in (None, SHARED):
            pheromone = np.zeros((grid.height, grid.width))
            policy = AcoPolicy(config, pheromone, distance_map(grid))
            return Simulation(config, grid, policy, rng, pheromone=pheromone)
        if reward == INDIVIDUAL:  # egoists leave no trail, so there is no pheromone at all
            return Simulation(config, grid, IndividualPolicy(config), rng)
        raise ValueError(f"Unknown reward: {reward}")
    raise ValueError(f"Unknown algorithm: {algorithm}")
