"""Headless simulation loop: agents search for cans, fill their bags and bring them to a base.

The simulation holds no rendering state; a visualization only reads `grid`, `agents`,
`pheromone` and `step_count`.
"""

import numpy as np

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid, Position
from kaucjowicze.pathfinding import (
    distance_map,
    first_step_to_nearest_can,
    step_towards_base,
    visible_cans,
)
from kaucjowicze.policies import MovementPolicy


class Simulation:
    def __init__(
        self,
        config: SimulationConfig,
        grid: Grid,
        policy: MovementPolicy,
        rng: np.random.Generator,
        pheromone: np.ndarray | None = None,
    ) -> None:
        """`pheromone` is an array [y, x] updated in place; `None` means no trails are left."""
        if not grid.bases:
            raise ValueError("Grid must have at least one base")
        if pheromone is not None and pheromone.shape != (grid.height, grid.width):
            raise ValueError(f"Pheromone shape {pheromone.shape} does not match the grid")
        if pheromone is not None and not np.issubdtype(pheromone.dtype, np.floating):
            raise ValueError(f"Pheromone must be a floating-point array, got {pheromone.dtype}")
        self.config = config
        self.grid = grid
        self.policy = policy
        self.rng = rng
        self.distance = distance_map(grid)  # computed once: the map does not change
        self.agents = [
            Agent(id=i, pos=grid.bases[i % len(grid.bases)]) for i in range(config.n_agents)
        ]
        self.initial_cans = grid.total_cans
        self.collected = 0
        self.step_count = 0
        self.pheromone = pheromone

    @property
    def is_finished(self) -> bool:
        """All cans delivered to a base, or the step limit T reached."""
        return self.collected >= self.initial_cans or self.step_count >= self.config.max_steps

    def run(self) -> None:
        while not self.is_finished:
            self.step()

    def step(self) -> None:
        """Advance every agent by one action (move, pick up one can, or deposit)."""
        for agent in self.agents:
            if agent.state is AgentState.SEARCHING:
                self._search(agent)
            else:
                self._carry(agent)
        if self.pheromone is not None:
            self.pheromone *= 1.0 - self.config.evaporation_rate
        self.step_count += 1

    def _search(self, agent: Agent) -> None:
        target = first_step_to_nearest_can(self.grid, agent.pos, self.config.vision_radius)
        if target == agent.pos:
            self.grid.take_can(agent.pos)
            agent.bag += 1
            agent.steps_without_can = 0
            agent.source_cans = visible_cans(self.grid, agent.pos, self.config.vision_radius)
            if agent.bag >= self.config.bag_capacity:
                agent.state = AgentState.CARRYING
            return
        if target is not None:
            agent.steps_without_can = 0
            self._move(agent, target)
            return

        agent.steps_without_can += 1
        if agent.bag > 0 and agent.steps_without_can >= self.config.return_patience:
            agent.state = AgentState.CARRYING
            return
        self._move(agent, self.policy.choose_move(agent, self.grid, self.rng))

    def _carry(self, agent: Agent) -> None:
        if not self.grid.is_base(agent.pos):
            self._lay_trail(agent)
            self._move(agent, step_towards_base(self.grid, self.distance, agent.pos))
        if self.grid.is_base(agent.pos):
            self._deposit(agent)

    def _lay_trail(self, agent: Agent) -> None:
        """Mark the cell being left, so the trail reaches the source and spares the base."""
        if self.pheromone is not None:
            x, y = agent.pos
            self.pheromone[y, x] += self.config.trail_deposit * agent.source_cans

    def _deposit(self, agent: Agent) -> None:
        self.collected += agent.bag
        agent.cans_collected += agent.bag
        agent.bag = 0
        agent.trips += 1
        agent.steps_without_can = 0
        agent.source_cans = 0
        agent.state = AgentState.SEARCHING

    @staticmethod
    def _move(agent: Agent, target: Position) -> None:
        if target == agent.pos:
            return
        agent.heading = (target[0] - agent.pos[0], target[1] - agent.pos[1])
        agent.pos = target
        agent.path_length += 1
