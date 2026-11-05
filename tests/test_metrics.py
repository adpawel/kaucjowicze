import numpy as np
import pytest

from kaucjowicze.config import SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.grid import Grid
from kaucjowicze.metrics import gini, record_run, steps_to_reach
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import Simulation


def _corridor_sim(max_steps: int = 100, cans: int = 2) -> Simulation:
    """One agent, a corridor and one pile of cans two cells from the base: every step is known."""
    grid = Grid(5, 1)
    grid.add_base((0, 0))
    grid.add_can((2, 0), cans)
    config = SimulationConfig(
        width=5, height=1, n_agents=1, bag_capacity=2, max_steps=max_steps, seed=0
    )
    rng = np.random.default_rng(0)
    return Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([5, 5, 5, 5], 0.0),  # equal split
        ([0, 0, 0, 8], 0.75),  # one agent has everything: (n - 1) / n
        ([1, 2, 3, 4], 0.25),
        ([0, 0, 0], 0.0),  # nobody collected anything, so nobody has more
        ([7], 0.0),
        ([], 0.0),
    ],
)
def test_gini_known_values(values, expected):
    assert gini(values) == pytest.approx(expected)


def test_gini_ignores_order():
    assert gini([9, 1, 4, 0]) == pytest.approx(gini([0, 1, 4, 9]))


def test_gini_matches_definition_with_all_pairs():
    values = [3, 0, 7, 7, 12, 1]
    n = len(values)
    pairs = sum(abs(a - b) for a in values for b in values)
    assert gini(values) == pytest.approx(pairs / (2 * n * sum(values)))


def test_gini_rejects_negative_values():
    with pytest.raises(ValueError, match="negative"):
        gini([1, -1])


def test_steps_to_reach_returns_first_step_at_threshold():
    collected = [0, 0, 5, 5, 9, 10]
    assert steps_to_reach(collected, total=10, percent=50) == 2
    assert steps_to_reach(collected, total=10, percent=90) == 4
    assert steps_to_reach(collected, total=10, percent=100) == 5


def test_steps_to_reach_is_none_when_threshold_not_reached():
    assert steps_to_reach([0, 1, 2], total=10, percent=50) is None


def test_steps_to_reach_rounds_threshold_up():
    # 50% of 5 cans is 2.5, and 2 delivered cans are not yet half of them
    assert steps_to_reach([0, 2, 3], total=5, percent=50) == 2


@pytest.mark.parametrize(("total", "percent", "needed"), [(270, 90, 243), (270, 50, 135)])
def test_steps_to_reach_exact_threshold_has_no_rounding_error(total, percent, needed):
    assert steps_to_reach([0, needed - 1, needed], total=total, percent=percent) == 2


def test_steps_to_reach_with_no_cans_is_immediate():
    assert steps_to_reach([0], total=0, percent=100) == 0


def test_record_run_timeline_of_a_known_run():
    record = record_run(_corridor_sim())

    # Two moves, two pick-ups, two moves back; the second of those also delivers the cans
    assert [row.step for row in record.timeline] == list(range(7))
    assert [row.cans_collected for row in record.timeline] == [0, 0, 0, 0, 0, 0, 2]
    assert [row.cans_on_map for row in record.timeline] == [2, 2, 2, 1, 0, 0, 0]
    assert [row.agents_carrying for row in record.timeline] == [0, 0, 0, 0, 1, 1, 0]
    assert [row.agents_searching for row in record.timeline] == [1, 1, 1, 1, 0, 0, 1]


def test_record_run_summary_of_a_known_run():
    record = record_run(_corridor_sim())

    assert record.initial_cans == 2
    assert record.steps == 6
    assert record.cans_collected == 2
    assert (record.t_50, record.t_90, record.t_100) == (6, 6, 6)
    assert record.total_path_length == 4
    assert record.path_per_can == pytest.approx(2.0)
    assert record.trips == 1
    assert (record.cans_min, record.cans_max) == (2, 2)
    assert record.gini == 0.0
    assert [(a.agent_id, a.cans, a.path_length, a.trips) for a in record.agents] == [(0, 2, 4, 1)]


def test_cans_in_a_bag_do_not_count_as_collected():
    record = record_run(_corridor_sim(max_steps=4))  # both cans picked up, none delivered

    assert record.timeline[-1].cans_on_map == 0
    assert record.cans_collected == 0
    assert (record.t_50, record.t_90, record.t_100) == (None, None, None)
    assert record.path_per_can is None


def test_unreached_threshold_when_limit_comes_first():
    sim = _corridor_sim(max_steps=10, cans=3)  # the third can needs a second trip

    record = record_run(sim)

    assert record.steps == 10
    assert record.cans_collected == 2
    assert record.t_50 == 6
    assert record.t_90 is None
    assert record.t_100 is None


def test_recording_does_not_change_the_run():
    plain = build_simulation("aco", seed=4)
    while plain.step_count < 200:
        plain.step()
    config = SimulationConfig(max_steps=200)

    recorded = build_simulation("aco", seed=4, config=config)
    record = record_run(recorded)

    assert [agent.pos for agent in plain.agents] == [agent.pos for agent in recorded.agents]
    assert record.steps == 200
    assert (plain.pheromone == recorded.pheromone).all()


@pytest.mark.parametrize(
    ("algorithm", "reward"), [("random", None), ("aco", "shared"), ("aco", "individual")]
)
def test_timeline_stays_consistent_on_the_test_map(algorithm, reward):
    config = SimulationConfig(max_steps=300)
    record = record_run(build_simulation(algorithm, seed=1, reward=reward, config=config))

    collected = [row.cans_collected for row in record.timeline]
    assert collected == sorted(collected)
    assert [row.step for row in record.timeline] == list(range(record.steps + 1))
    for row in record.timeline:
        assert row.agents_searching + row.agents_carrying == config.n_agents
        assert row.cans_on_map + row.cans_collected <= record.initial_cans
    assert record.timeline[0].cans_on_map == record.initial_cans
    assert sum(agent.cans for agent in record.agents) == record.cans_collected
    assert sum(agent.trips for agent in record.agents) == record.trips
    assert sum(agent.path_length for agent in record.agents) == record.total_path_length


def test_run_without_agents_has_no_per_agent_extremes():
    config = SimulationConfig(n_agents=0, max_steps=3)

    record = record_run(build_simulation("random", 0, config=config))

    assert record.agents == []
    assert (record.cans_min, record.cans_max) == (None, None)
    assert record.gini == 0.0
