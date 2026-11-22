"""Trail signals that feed an objective into ACO through the amount of trail (NAGRODY.md, 2-4)."""

from dataclasses import replace

import numpy as np
import pytest

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import TRAILS, SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.grid import Grid
from kaucjowicze.metrics import objective_j, record_run, speed_norm
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.rewards import trail_amount
from kaucjowicze.simulation import Simulation


def _carrying(source_cans: int = 4, bag: int = 5, trip_length: int = 20, cans: int = 0) -> Agent:
    return Agent(
        id=0,
        pos=(3, 0),
        state=AgentState.CARRYING,
        bag=bag,
        source_cans=source_cans,
        trip_length=trip_length,
        cans_collected=cans,
    )


def _config(trail: str, **kwargs) -> SimulationConfig:
    return SimulationConfig(**TRAILS[trail], **kwargs)


def test_named_trails_are_the_four_signals_of_the_plan():
    assert list(TRAILS) == ["source", "speed", "equal+", "equal-"]
    assert _config("equal+").fairness_gamma == 1.0
    assert _config("equal-").fairness_gamma == -1.0


def test_source_trail_is_q_times_cans_left_at_the_source():
    config = _config("source", trail_deposit=0.5)
    assert trail_amount(_carrying(source_cans=4), config, mean_cans=0.0) == pytest.approx(2.0)


def test_speed_trail_is_qs_times_cans_carried_per_step_of_the_trip():
    config = _config("speed", speed_deposit=3.0)
    agent = _carrying(source_cans=4, bag=5, trip_length=20)
    assert trail_amount(agent, config, mean_cans=0.0) == pytest.approx(3.0 * 5 / 20)


def test_speed_trail_does_not_depend_on_how_many_cans_are_left():
    config = _config("speed", speed_deposit=3.0)
    few, many = _carrying(source_cans=1), _carrying(source_cans=30)
    assert trail_amount(few, config, 0.0) == trail_amount(many, config, 0.0)


@pytest.mark.parametrize(
    ("trail", "cans", "mean", "weight"),
    [
        ("equal+", 9, 4.0, 10 / 5),  # richer than the mean: a stronger trail
        ("equal-", 9, 4.0, 5 / 10),  # richer than the mean: a weaker trail
        ("equal+", 0, 4.0, 1 / 5),
        ("equal-", 0, 4.0, 5 / 1),
        ("equal+", 0, 0.0, 1.0),  # at the start everybody weighs 1
        ("equal-", 3, 3.0, 1.0),
    ],
)
def test_equal_trail_weighs_the_source_trail_by_relative_earnings(trail, cans, mean, weight):
    config = _config(trail, trail_deposit=0.5)
    agent = _carrying(source_cans=4, cans=cans)
    assert trail_amount(agent, config, mean_cans=mean) == pytest.approx(0.5 * 4 * weight)


@pytest.mark.parametrize("trail", list(TRAILS))
def test_no_signal_marks_an_exhausted_source(trail):
    config = _config(trail, speed_deposit=3.0)
    assert trail_amount(_carrying(source_cans=0, cans=9), config, mean_cans=2.0) == 0.0


def test_unknown_trail_signal_is_rejected():
    with pytest.raises(ValueError, match="trail signal"):
        SimulationConfig(trail_signal="nope")


def test_negative_speed_deposit_is_rejected():
    with pytest.raises(ValueError, match="Speed deposit"):
        SimulationConfig(speed_deposit=-1.0)


def test_speed_deposit_has_a_default_for_each_map():
    for map_name in ("test", "campus"):
        assert SimulationConfig(map_name=map_name).speed_deposit > 0


def _corridor(trail: str = "source", **kwargs) -> Simulation:
    """One agent, a corridor and two cans two cells from the base: every step is known."""
    grid = Grid(5, 1)
    grid.add_base((0, 0))
    grid.add_can((2, 0), 2)
    settings = {"bag_capacity": 2, **kwargs}
    config = _config(trail, width=5, height=1, n_agents=1, evaporation_rate=0.0, seed=0, **settings)
    rng = np.random.default_rng(0)
    pheromone = np.zeros((grid.height, grid.width))
    policy = RandomWalkPolicy(config.direction_persistence)
    return Simulation(config, grid, policy, rng, pheromone=pheromone)


def test_trip_length_is_known_when_the_return_starts():
    sim = _corridor()
    agent = sim.agents[0]
    # two moves to the pile and two pick-ups; the second fills the bag
    for _ in range(4):
        sim.step()
    assert agent.state is AgentState.CARRYING
    assert agent.trip_steps == 4
    assert agent.trip_length == 4 + 2  # the steps so far and two more back to the base

    sim.step()
    assert agent.trip_length == 6  # stays the same on the way back
    sim.step()  # reaches the base and delivers
    assert sim.step_count == 6  # the trip took exactly L steps
    assert (agent.trip_steps, agent.trip_length) == (0, 0)


def test_trip_length_counts_a_return_with_a_partial_bag():
    grid = Grid(8, 1)
    grid.add_base((0, 0))
    config = SimulationConfig(width=8, height=1, n_agents=1, return_patience=3, seed=0)
    sim = Simulation(config, grid, RandomWalkPolicy(0.0), np.random.default_rng(0))
    agent = sim.agents[0]
    agent.pos, agent.bag, agent.steps_without_can, agent.trip_steps = (5, 0), 1, 2, 10

    sim.step()  # patience runs out: the agent turns back where it stands
    assert agent.state is AgentState.CARRYING
    assert agent.trip_length == 11 + 5
    for _ in range(5):
        sim.step()
    assert (agent.bag, agent.trips) == (0, 1)


def test_speed_trail_on_the_corridor():
    sim = _corridor("speed", speed_deposit=3.0)
    for _ in range(6):
        sim.step()
    # n = 1 after the first pick-up but 0 after the second, so the exhausted pile is not marked
    assert sim.pheromone.sum() == 0.0

    sim = _corridor("speed", speed_deposit=3.0, bag_capacity=1)
    for _ in range(5):  # two moves, one pick-up, two steps back
        sim.step()
    assert sim.pheromone[0].tolist() == pytest.approx([0.0, 0.6, 0.6, 0.0, 0.0])  # 3 * 1 / 5


def test_source_trail_keeps_the_runs_of_n1():
    config = SimulationConfig(n_agents=5, max_steps=300)
    default = record_run(build_simulation("aco", 3, config=config))
    named = record_run(build_simulation("aco", 3, config=replace(config, **TRAILS["source"])))
    assert named == default


@pytest.mark.parametrize("trail", ["speed", "equal+", "equal-"])
def test_trail_signals_change_nothing_but_the_trail(trail):
    config = SimulationConfig(n_agents=5, max_steps=300)
    other = replace(config, **TRAILS[trail])
    random_walk = record_run(build_simulation("random", 3, config=config))
    assert record_run(build_simulation("random", 3, config=other)) == random_walk
    egoists = record_run(build_simulation("aco", 3, "individual", config=config))
    assert record_run(build_simulation("aco", 3, "individual", config=other)) == egoists


@pytest.mark.parametrize(("t_90", "expected"), [(0, 1.0), (250, 0.75), (1000, 0.0), (None, 0.0)])
def test_speed_norm_is_one_minus_the_share_of_the_limit_used(t_90, expected):
    assert speed_norm(t_90, max_steps=1000) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("t_90", "gini", "w1", "expected"),
    [
        (250, 0.4, 0.5, 0.5 * 0.75 + 0.5 * 0.6),
        (250, 0.4, 1.0, 0.75),
        (250, 0.4, 0.0, 0.6),
        (None, 0.4, 0.5, 0.5 * 0.0 + 0.5 * 0.6),  # below the threshold: no credit for speed
        (0, 0.0, 0.25, 1.0),
    ],
)
def test_objective_j_known_values(t_90, gini, w1, expected):
    assert objective_j(t_90, 1000, gini, w1) == pytest.approx(expected)


def test_objective_j_weight_must_be_a_share():
    with pytest.raises(ValueError):
        objective_j(10, 100, 0.5, 1.5)
