"""Movement policies for searching agents that see no can.

A policy only decides where to explore. Picking up, vision, returning to a base and laying
trails are handled by the simulation.
"""

from typing import Protocol

import numpy as np

from kaucjowicze.agent import Agent
from kaucjowicze.config import SimulationConfig
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


class AcoPolicy:
    """Follow pheromone trails towards cans, with epsilon-exploration.

    A neighbour is chosen with probability proportional to (tau + tau0) ** alpha. Only trail on
    cells farther from the base counts: trails are laid on the way home, so walking them away
    from the base leads to the cans. With no such trail in reach the agent explores exactly
    like the random walk, which keeps the comparison with the baseline fair, so epsilon only
    applies where there is a trail to leave.
    """

    def __init__(
        self, config: SimulationConfig, pheromone: np.ndarray, distance: np.ndarray
    ) -> None:
        self.alpha = config.pheromone_alpha
        self.tau0 = config.pheromone_base
        self.epsilon = config.exploration_rate
        self.pheromone = pheromone  # read only; the simulation lays and evaporates trails
        self.distance = distance
        self._explorer = RandomWalkPolicy(config.direction_persistence)

    def choose_move(self, agent: Agent, grid: Grid, rng: np.random.Generator) -> Position:
        options = free_neighbours(grid, agent.pos)
        if not options:
            return agent.pos

        trail = self._outward_trail(agent.pos, options)
        if trail.max() <= self.tau0:
            return self._explorer.choose_move(agent, grid, rng)
        if rng.random() < self.epsilon:
            return options[int(rng.integers(len(options)))]
        bases = trail + self.tau0
        # Scaling keeps the probabilities and stops a large alpha from under- or overflowing
        weights = (bases / bases.max()) ** self.alpha
        return options[int(rng.choice(len(options), p=weights / weights.sum()))]

    def _outward_trail(self, pos: Position, options: list[Position]) -> np.ndarray:
        """Pheromone on each option, or zero if the option does not lead away from the base."""
        here = self.distance[pos[1], pos[0]]
        return np.array(
            [self.pheromone[y, x] if self.distance[y, x] > here else 0.0 for x, y in options]
        )
