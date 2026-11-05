"""Movement policies for searching agents that see no can.

A policy only decides where to explore. Picking up, vision, returning to a base and laying
trails are handled by the simulation.
"""

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid, Position
from kaucjowicze.pathfinding import (
    distance_map,
    free_neighbours,
    step_closer,
    visible_cans,
    within_radius,
)


class MovementPolicy(Protocol):
    def choose_move(
        self,
        agent: Agent,
        grid: Grid,
        rng: np.random.Generator,
        agents: Sequence[Agent] = (),
    ) -> Position:
        """Return the next cell for `agent`: a free neighbour or its current cell.

        `agents` are all agents on the map, for policies that react to the others.
        """
        ...


class RandomWalkPolicy:
    """Random walk with a tendency to keep the current heading, so agents do not circle."""

    def __init__(self, persistence: float) -> None:
        if not 0.0 <= persistence <= 1.0:
            raise ValueError("Persistence must be in [0, 1]")
        self.persistence = persistence

    def choose_move(
        self,
        agent: Agent,
        grid: Grid,
        rng: np.random.Generator,
        agents: Sequence[Agent] = (),
    ) -> Position:
        x, y = agent.pos
        if agent.heading is not None and rng.random() < self.persistence:
            ahead = (x + agent.heading[0], y + agent.heading[1])
            if grid.is_free(ahead):
                return ahead
        options = free_neighbours(grid, agent.pos)
        if not options:
            return agent.pos
        return options[int(rng.integers(len(options)))]


class IndividualPolicy:
    """Individual reward (N2): return to the privately remembered source, ignoring the others.

    The simulation updates the memory at every pick-up. An agent only gets here when it sees no
    can, so reaching the remembered place means the source is gone. With nothing remembered the
    agent explores like the random walk.
    """

    def __init__(self, config: SimulationConfig) -> None:
        self._explorer = RandomWalkPolicy(config.direction_persistence)
        self._routes: dict[Position, np.ndarray] = {}  # distance maps of visited sources

    def choose_move(
        self,
        agent: Agent,
        grid: Grid,
        rng: np.random.Generator,
        agents: Sequence[Agent] = (),
    ) -> Position:
        if agent.remembered_source == agent.pos:
            agent.remembered_source = None
            agent.remembered_cans = 0
        if agent.remembered_source is None:
            return self._explorer.choose_move(agent, grid, rng)
        return step_closer(grid, self._route_to(grid, agent.remembered_source), agent.pos)

    def _route_to(self, grid: Grid, source: Position) -> np.ndarray:
        if source not in self._routes:
            self._routes[source] = distance_map(grid, [source])
        return self._routes[source]


class AcoPolicy:
    """Follow pheromone trails towards cans, with epsilon-exploration.

    A neighbour is chosen with probability proportional to (tau + tau0) ** alpha. Only trail on
    cells farther from the base counts: trails are laid on the way home, so walking them away
    from the base leads to the cans. With no such trail in reach the agent explores exactly
    like the random walk, which keeps the comparison with the baseline fair, so epsilon only
    applies where there is a trail to leave.

    Shared reward (N1): trail ahead of more searching agents than cans is scaled down by the
    crowd penalty, so the agent looks elsewhere instead of joining them.
    """

    def __init__(
        self, config: SimulationConfig, pheromone: np.ndarray, distance: np.ndarray
    ) -> None:
        self.alpha = config.pheromone_alpha
        self.tau0 = config.pheromone_base
        self.epsilon = config.exploration_rate
        self.crowd_radius = config.crowd_radius
        self.crowd_penalty = config.crowd_penalty
        self.pheromone = pheromone  # read only; the simulation lays and evaporates trails
        self.distance = distance
        self._explorer = RandomWalkPolicy(config.direction_persistence)

    def choose_move(
        self,
        agent: Agent,
        grid: Grid,
        rng: np.random.Generator,
        agents: Sequence[Agent] = (),
    ) -> Position:
        options = free_neighbours(grid, agent.pos)
        if not options:
            return agent.pos

        trail = self._outward_trail(agent.pos, options)
        self._penalise_crowds(trail, agent.pos, options, grid, agents)
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

    def _penalise_crowds(
        self,
        trail: np.ndarray,
        pos: Position,
        options: list[Position],
        grid: Grid,
        agents: Sequence[Agent],
    ) -> None:
        if self.crowd_penalty == 1.0:
            return
        for i, option in enumerate(options):
            if trail[i] > self.tau0 and self._is_crowded(pos, option, grid, agents):
                trail[i] *= self.crowd_penalty

    def _is_crowded(
        self, pos: Position, option: Position, grid: Grid, agents: Sequence[Agent]
    ) -> bool:
        """More searching agents than cans in the window just ahead of the move.

        The window does not contain `pos`, so the agent never counts itself. A window without
        cans is no crowd: agents walking along a trail to a far source must not put each other off.
        """
        reach = self.crowd_radius + 1
        ahead = (pos[0] + reach * (option[0] - pos[0]), pos[1] + reach * (option[1] - pos[1]))
        cans = visible_cans(grid, ahead, self.crowd_radius)
        if cans == 0:
            return False
        searching = sum(
            other.state is AgentState.SEARCHING
            and within_radius(ahead, other.pos, self.crowd_radius)
            for other in agents
        )
        return searching > cans
