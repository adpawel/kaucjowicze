"""Metrics of a single run. They only read the simulation, so recording never changes a run."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from kaucjowicze.agent import AgentState
from kaucjowicze.simulation import Simulation


def gini(values: Sequence[float]) -> float:
    """Gini coefficient: 0 for an equal split, (n - 1) / n when one value holds everything.

    With nothing to share (no values or only zeros) nobody has more, so the result is 0.
    """
    ordered = np.sort(np.asarray(values, dtype=float))
    if ordered.size and ordered[0] < 0:
        raise ValueError("Gini coefficient is not defined for negative values")
    total = ordered.sum()
    if total == 0:
        return 0.0
    n = ordered.size
    ranks = np.arange(1, n + 1)
    return float(2 * (ranks * ordered).sum() / (n * total) - (n + 1) / n)


def steps_to_reach(collected: Sequence[int], total: int, percent: int) -> int | None:
    """First index at which `percent`% of `total` is collected; `None` if that never happens.

    `collected[i]` is the count after step i. Integer arithmetic keeps exact thresholds exact.
    """
    needed = -(-percent * total // 100)  # rounded up: 2 of 5 cans are not yet 50%
    return next((step for step, count in enumerate(collected) if count >= needed), None)


@dataclass(frozen=True)
class TimelineRow:
    """State of a run after `step` steps."""

    step: int
    cans_collected: int  # delivered to a base; cans in bags do not count
    cans_on_map: int
    agents_searching: int
    agents_carrying: int


@dataclass(frozen=True)
class AgentRecord:
    agent_id: int
    cans: int
    path_length: int
    trips: int


@dataclass(frozen=True)
class RunRecord:
    """Everything measured in one run."""

    initial_cans: int
    timeline: list[TimelineRow]
    agents: list[AgentRecord]

    @property
    def steps(self) -> int:
        return self.timeline[-1].step

    @property
    def cans_collected(self) -> int:
        return self.timeline[-1].cans_collected

    def _steps_to(self, percent: int) -> int | None:
        collected = [row.cans_collected for row in self.timeline]
        return steps_to_reach(collected, self.initial_cans, percent)

    @property
    def t_50(self) -> int | None:
        return self._steps_to(50)

    @property
    def t_90(self) -> int | None:
        return self._steps_to(90)

    @property
    def t_100(self) -> int | None:
        return self._steps_to(100)

    @property
    def total_path_length(self) -> int:
        return sum(agent.path_length for agent in self.agents)

    @property
    def path_per_can(self) -> float | None:
        """Moves of all agents per delivered can; `None` if no can was delivered."""
        if self.cans_collected == 0:
            return None
        return self.total_path_length / self.cans_collected

    @property
    def trips(self) -> int:
        return sum(agent.trips for agent in self.agents)

    @property
    def gini(self) -> float:
        return gini([agent.cans for agent in self.agents])

    @property
    def cans_min(self) -> int | None:
        return min((agent.cans for agent in self.agents), default=None)

    @property
    def cans_max(self) -> int | None:
        return max((agent.cans for agent in self.agents), default=None)


def _snapshot(sim: Simulation) -> TimelineRow:
    carrying = sum(agent.state is AgentState.CARRYING for agent in sim.agents)
    return TimelineRow(
        step=sim.step_count,
        cans_collected=sim.collected,
        cans_on_map=sim.grid.total_cans,
        agents_searching=len(sim.agents) - carrying,
        agents_carrying=carrying,
    )


def record_run(sim: Simulation) -> RunRecord:
    """Run a fresh simulation to its end, noting its state before the first step and after each."""
    timeline = [_snapshot(sim)]
    while not sim.is_finished:
        sim.step()
        timeline.append(_snapshot(sim))
    agents = [
        AgentRecord(agent.id, agent.cans_collected, agent.path_length, agent.trips)
        for agent in sim.agents
    ]
    return RunRecord(sim.initial_cans, timeline, agents)
