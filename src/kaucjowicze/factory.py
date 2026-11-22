"""Building a ready-to-run simulation of a chosen variant."""

from dataclasses import replace

import numpy as np

from kaucjowicze.cans import scatter_cans, schedule_events
from kaucjowicze.config import SimulationConfig
from kaucjowicze.maps import build_map
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import AcoPolicy, IndividualPolicy, MixedPolicy, RandomWalkPolicy
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
    `egoist_share` in `config` makes the shared variant a mixed population; the others ignore it.
    `seed` replaces the seed in `config`. Cans are scattered before any policy draws a number,
    so all variants get the same map for the same seed. Parties are drawn from a stream of their
    own, so they are the same for every variant too and leave the static runs as they were.
    """
    config = replace(config or SimulationConfig(), seed=seed)
    rng = np.random.default_rng(config.seed)
    grid = build_map(config)
    scatter_cans(grid, config, rng)
    events = schedule_events(grid, config, _event_rng(config.seed))
    if algorithm == "random":
        if reward is not None:
            raise ValueError("The random walk does not use a reward")
        policy = RandomWalkPolicy(config.direction_persistence)
        return Simulation(config, grid, policy, rng, events=events)
    if algorithm == "aco":
        if reward in (None, SHARED):
            pheromone = np.zeros((grid.height, grid.width))
            if config.n_egoists == 0:
                policy = AcoPolicy(config, pheromone, distance_map(grid))
            else:  # a mixed population (P10)
                policy = MixedPolicy(config, pheromone, distance_map(grid))
            return Simulation(
                config,
                grid,
                policy,
                rng,
                pheromone=pheromone,
                events=events,
                egoists=config.n_egoists,
            )
        if reward == INDIVIDUAL:  # egoists leave no trail, so there is no pheromone at all
            return Simulation(config, grid, IndividualPolicy(config), rng, events=events)
        raise ValueError(f"Unknown reward: {reward}")
    raise ValueError(f"Unknown algorithm: {algorithm}")


def _event_rng(seed: int | None) -> np.random.Generator:
    """Stream of the parties: derived from the seed, but separate from the one of the run."""
    return np.random.default_rng(None if seed is None else [seed, 1])
