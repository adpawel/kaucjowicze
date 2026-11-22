"""Headless simulation loop: agents search for cans, fill their bags and bring them to a base.

The simulation holds no rendering state; a visualization only reads `grid`, `agents`,
`pheromone` and `step_count`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.cans import SpawnEvent
from kaucjowicze.config import EQUAL, SimulationConfig
from kaucjowicze.grid import Grid, Position
from kaucjowicze.pathfinding import (
    distance_map,
    first_step_to_nearest_can,
    seen_cans,
    step_closer,
    within_radius,
)
from kaucjowicze.policies import MovementPolicy
from kaucjowicze.rewards import trail_amount


@dataclass
class EventLog:
    """What happened to the cans of one party; steps count like `step_count` after a step."""

    event: SpawnEvent
    overlap: int = 0  # cans that landed on a cell already holding cans
    pickup_steps: list[int] = field(default_factory=list)  # one entry per can picked up
    agents: set[int] = field(default_factory=set)  # agents that picked up at least one can


class CanLedger:
    """Which source each can on the map comes from: 0 for the start, then the party ids.

    A pick-up takes the oldest can on the cell, so a party never looks faster than it was.
    It knows the cans on the grid when it is made and those of parties; a can added to the grid
    in any other way is not traced, and a pick-up of it may be charged to the wrong source.
    """

    def __init__(self, grid: Grid, n_events: int) -> None:
        self.counts = np.zeros((n_events + 1, grid.height, grid.width), dtype=np.int32)
        self.counts[0] = grid.cans

    def add(self, source: int, pos: Position) -> None:
        self.counts[source, pos[1], pos[0]] += 1

    def take(self, pos: Position) -> int | None:
        """Source of the can taken from `pos`; `None` for a can the ledger never saw."""
        x, y = pos
        sources = np.flatnonzero(self.counts[:, y, x])
        if sources.size == 0:
            return None
        source = int(sources[0])
        self.counts[source, y, x] -= 1
        return source


class Simulation:
    def __init__(
        self,
        config: SimulationConfig,
        grid: Grid,
        policy: MovementPolicy,
        rng: np.random.Generator,
        pheromone: np.ndarray | None = None,
        events: Sequence[SpawnEvent] = (),
    ) -> None:
        """`pheromone` is an array [y, x] updated in place; `None` means no trails are left.

        `events` are parties: their cans appear once `step_count` reaches their step.
        """
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
        self.events = sorted(events, key=lambda event: event.step)
        if [event.id for event in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError("Party ids must be 1, 2, ... in the order of their steps")
        if self.events and self.events[-1].step >= config.max_steps:
            raise ValueError("Every party must start before the step limit")
        self.event_logs = [EventLog(event) for event in self.events]
        self.events_spawned = 0
        self.ledger = CanLedger(grid, len(self.events))
        self.trail_laid = 0.0  # all trail laid so far, before evaporation
        self.trail_steps = 0  # cells left by carrying agents, with or without trail
        self._spawn_due()

    @property
    def total_cans(self) -> int:
        """Cans of the whole run: those from the start and those of every party."""
        return self.initial_cans + sum(event.cans for event in self.events)

    @property
    def next_event(self) -> SpawnEvent | None:
        if self.events_spawned < len(self.events):
            return self.events[self.events_spawned]
        return None

    @property
    def is_finished(self) -> bool:
        """All cans of the run delivered to a base, or the step limit T reached."""
        return self.collected >= self.total_cans or self.step_count >= self.config.max_steps

    def _spawn_due(self) -> None:
        """Leave the cans of every party whose step has come."""
        while (event := self.next_event) is not None and event.step <= self.step_count:
            log = self.event_logs[self.events_spawned]
            log.overlap = sum(int(self.grid.cans[y, x] > 0) for x, y in event.cells)
            for pos in event.cells:
                self.grid.add_can(pos)
                self.ledger.add(event.id, pos)
            self.events_spawned += 1

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
        self._spawn_due()

    def _search(self, agent: Agent) -> None:
        agent.trip_steps += 1  # draws no number, so the runs of every signal stay as they were
        target = first_step_to_nearest_can(self.grid, agent.pos, self.config.vision_radius)
        if target == agent.pos:
            self.grid.take_can(agent.pos)
            self._note_pickup(agent)
            agent.bag += 1
            agent.steps_without_can = 0
            agent.source_cans = seen_cans(self.grid, agent.pos, self.config.vision_radius)
            self._remember_source(agent)
            if agent.bag >= self.config.bag_capacity:
                self._start_return(agent)
            return
        if target is not None:
            agent.steps_without_can = 0
            self._move(agent, target)
            return

        agent.steps_without_can += 1
        if agent.bag > 0 and agent.steps_without_can >= self.config.return_patience:
            self._start_return(agent)
            return
        self._move(agent, self.policy.choose_move(agent, self.grid, self.rng, self.agents))

    def _note_pickup(self, agent: Agent) -> None:
        source = self.ledger.take(agent.pos)
        if source:  # 0 and `None` are not parties
            log = self.event_logs[source - 1]
            log.pickup_steps.append(self.step_count + 1)  # the step ends once every agent acted
            log.agents.add(agent.id)

    def _remember_source(self, agent: Agent) -> None:
        """Keep the richest source seen; what is seen at the remembered place replaces its count."""
        seen = agent.source_cans
        known = agent.remembered_source
        if (
            known is None
            or seen >= agent.remembered_cans
            or within_radius(known, agent.pos, self.config.vision_radius)
        ):
            agent.remembered_source = agent.pos if seen > 0 else None
            agent.remembered_cans = seen

    def _start_return(self, agent: Agent) -> None:
        """Turn back to a base: a full bag or no new can for too long.

        The trip length L is the steps so far and the known distance home, so it is fixed for the
        whole return. Off a base the return takes exactly that distance.
        """
        x, y = agent.pos
        agent.trip_length = agent.trip_steps + int(self.distance[y, x])
        agent.state = AgentState.CARRYING

    def _carry(self, agent: Agent) -> None:
        if not self.grid.is_base(agent.pos):
            self._lay_trail(agent)
            self._move(agent, step_closer(self.grid, self.distance, agent.pos))
        if self.grid.is_base(agent.pos):
            self._deposit(agent)

    def _lay_trail(self, agent: Agent) -> None:
        """Mark the cell being left, so the trail reaches the source and spares the base."""
        if self.pheromone is not None:
            x, y = agent.pos
            mean_cans = self._mean_delivered() if self.config.trail_signal == EQUAL else 0.0
            amount = trail_amount(agent, self.config, mean_cans)
            self.pheromone[y, x] += amount
            self.trail_laid += amount
            self.trail_steps += 1

    def _mean_delivered(self) -> float:
        return sum(agent.cans_collected for agent in self.agents) / len(self.agents)

    def _deposit(self, agent: Agent) -> None:
        self.collected += agent.bag
        agent.cans_collected += agent.bag
        agent.bag = 0
        agent.trips += 1
        agent.steps_without_can = 0
        agent.source_cans = 0
        agent.trip_steps = 0
        agent.trip_length = 0
        agent.state = AgentState.SEARCHING

    @staticmethod
    def _move(agent: Agent, target: Position) -> None:
        if target == agent.pos:
            return
        agent.heading = (target[0] - agent.pos[0], target[1] - agent.pos[1])
        agent.pos = target
        agent.path_length += 1
