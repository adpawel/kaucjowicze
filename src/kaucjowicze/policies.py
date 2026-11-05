"""Movement policies for searching agents that see no can.

A policy only decides where to explore. Picking up, vision and returning to a base are
handled by the simulation, so ACO can be added later as another policy.
"""

from typing import Protocol

import numpy as np

from kaucjowicze.agent import Agent
from kaucjowicze.grid import Grid, Position
from kaucjowicze.pathfinding import free_neighbours


class MovementPolicy(Protocol):
    def choose_move(self, agent: Agent, grid: Grid, rng: np.random.Generator) -> Position:
        """Return the next cell for `agent`: a free neighbour or its current cell."""
        ...


class RandomWalkPolicy:
    """Random walk with a tendency to keep the current heading, so agents do not circle."""

    def __init__(self, persistence: float) -> None:
        if not 0.0 <= persistence <= 1.0:
            raise ValueError("Persistence must be in [0, 1]")
        self.persistence = persistence

    def choose_move(self, agent: Agent, grid: Grid, rng: np.random.Generator) -> Position:
        x, y = agent.pos
        if agent.heading is not None and rng.random() < self.persistence:
            ahead = (x + agent.heading[0], y + agent.heading[1])
            if grid.is_free(ahead):
                return ahead
        options = free_neighbours(grid, agent.pos)
        if not options:
            return agent.pos
        return options[int(rng.integers(len(options)))]
