"""Mixed population (comparison P10): egoists of N2 that read the trails of N1 cooperators."""

from dataclasses import replace

import numpy as np
import pytest

from kaucjowicze.agent import AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.experiments import run_sweep
from kaucjowicze.factory import build_simulation
from kaucjowicze.grid import Grid
from kaucjowicze.metrics import record_run
from kaucjowicze.policies import MixedPolicy
from kaucjowicze.simulation import Simulation

CONFIG = SimulationConfig(n_agents=8, max_steps=400)


@pytest.mark.parametrize(("share", "egoists"), [(0.0, 0), (0.25, 2), (0.5, 4), (1.0, 8)])
def test_share_gives_the_number_of_egoists(share, egoists):
    assert replace(CONFIG, egoist_share=share).n_egoists == egoists


@pytest.mark.parametrize("share", [-0.1, 1.1])
def test_share_outside_zero_to_one_is_rejected(share):
    with pytest.raises(ValueError, match="Egoist share"):
        SimulationConfig(egoist_share=share)


def test_no_egoists_is_n1():
    n1 = record_run(build_simulation("aco", 4, config=CONFIG))
    mixed = build_simulation("aco", 4, config=replace(CONFIG, egoist_share=0.0))
    assert record_run(mixed) == n1


def test_only_egoists_is_n2():
    n2 = record_run(build_simulation("aco", 4, "individual", config=CONFIG))
    mixed = build_simulation("aco", 4, config=replace(CONFIG, egoist_share=1.0))
    assert isinstance(mixed.policy, MixedPolicy)
    record = record_run(mixed)
    assert mixed.pheromone.sum() == 0.0  # nobody ever laid a trail
    assert record.timeline == n2.timeline
    assert [(a.cans, a.path_length, a.trips) for a in record.agents] == [
        (a.cans, a.path_length, a.trips) for a in n2.agents
    ]


def test_first_agents_are_the_egoists_and_are_recorded():
    sim = build_simulation("aco", 4, config=replace(CONFIG, egoist_share=0.25))
    assert [agent.egoist for agent in sim.agents] == [True] * 2 + [False] * 6
    assert [agent.egoist for agent in record_run(sim).agents] == [True] * 2 + [False] * 6


@pytest.mark.parametrize(("algorithm", "reward"), [("random", None), ("aco", "individual")])
def test_other_variants_ignore_the_share(algorithm, reward):
    plain = record_run(build_simulation(algorithm, 4, reward, CONFIG))
    other = record_run(build_simulation(algorithm, 4, reward, replace(CONFIG, egoist_share=0.5)))
    assert other == plain
    assert not any(agent.egoist for agent in other.agents)


def _corridor_with(egoist: bool) -> Simulation:
    grid = Grid(10, 1)
    grid.add_base((0, 0))
    config = SimulationConfig(width=10, height=1, n_agents=1, evaporation_rate=0.0, seed=0)
    pheromone = np.zeros((1, 10))
    policy = MixedPolicy(config, pheromone, np.arange(10, dtype=float)[None, :])
    sim = Simulation(
        config, grid, policy, np.random.default_rng(0), pheromone=pheromone, egoists=int(egoist)
    )
    agent = sim.agents[0]
    agent.pos, agent.bag, agent.source_cans, agent.state = (4, 0), 3, 5, AgentState.CARRYING
    return sim


def test_egoists_lay_no_trail_and_cooperators_do():
    egoist = _corridor_with(egoist=True)
    cooperator = _corridor_with(egoist=False)
    for _ in range(4):
        egoist.step()
        cooperator.step()
    assert egoist.pheromone.sum() == 0.0
    assert cooperator.pheromone.sum() == pytest.approx(4 * 5.0)


def test_egoist_without_memory_follows_a_trail():
    grid = Grid(7, 3)
    grid.add_base((3, 1))
    config = SimulationConfig(width=7, height=3, n_agents=1, exploration_rate=0.0, seed=0)
    pheromone = np.zeros((3, 7))
    pheromone[1, 4] = 50.0  # a strong trail leading east, away from the base
    sim = Simulation(
        config,
        grid,
        MixedPolicy(config, pheromone, _distance(grid)),
        np.random.default_rng(1),
        pheromone=pheromone,
        egoists=1,
    )
    moves = set()
    for seed in range(20):
        sim.agents[0].pos, sim.agents[0].heading = (3, 1), None
        moves.add(sim.policy.choose_move(sim.agents[0], grid, np.random.default_rng(seed)))
    assert moves == {(4, 1)}


def test_egoist_with_memory_goes_to_its_source_and_ignores_trails():
    grid = Grid(7, 3)
    grid.add_base((3, 1))
    config = SimulationConfig(width=7, height=3, n_agents=1, exploration_rate=0.0, seed=0)
    pheromone = np.zeros((3, 7))
    pheromone[1, 4] = 50.0
    policy = MixedPolicy(config, pheromone, _distance(grid))
    sim = Simulation(config, grid, policy, np.random.default_rng(1), pheromone=pheromone, egoists=1)
    agent = sim.agents[0]
    agent.remembered_source, agent.remembered_cans = (0, 1), 7
    assert policy.choose_move(agent, grid, np.random.default_rng(0)) == (2, 1)


def _distance(grid: Grid) -> np.ndarray:
    from kaucjowicze.pathfinding import distance_map

    return distance_map(grid)


def test_sweep_of_the_share_records_egoists_per_run_and_agent():
    config = SimulationConfig(
        width=30, height=20, n_clusters=2, cans_per_cluster=5, n_agents=4, max_steps=60
    )
    tables = run_sweep([0], "egoist_share", [0.0, 0.5], config)
    assert [row["egoists"] for row in tables.runs] == [None, 0, None, None, 2, None]
    mixed_run = tables.runs[4]["run_id"]
    flags = [row["egoist"] for row in tables.agents if row["run_id"] == mixed_run]
    assert flags == [1, 1, 0, 0]
