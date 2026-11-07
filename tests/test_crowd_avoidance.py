from collections import Counter

import numpy as np
import pytest

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import AcoPolicy
from kaucjowicze.simulation import Simulation

SAMPLES = 2000

# On an open grid with the base at (0, 0) the distance to base is max(x, y), so from (5, 5) the
# cells below lead away from the base. With crowd_radius = 2 the area ahead of a direction d is
# the 5x5 window centred on START + 3 * d.
START = (5, 5)
DIAGONAL, DOWN = (6, 6), (5, 6)  # the diagonal looks at x, y in 6..10, down at x 3..7, y 6..10


def _searcher(pos: tuple[int, int], agent_id: int = 1) -> Agent:
    return Agent(id=agent_id, pos=pos)


def _open_grid(size: int = 11, base: tuple[int, int] = (0, 0)) -> Grid:
    grid = Grid(size, size)
    grid.add_base(base)
    return grid


def _crowd_policy(grid: Grid, **config_kwargs) -> tuple[AcoPolicy, np.ndarray]:
    config_kwargs.setdefault("exploration_rate", 0.0)
    config_kwargs.setdefault("crowd_radius", 2)
    config_kwargs.setdefault("crowd_penalty", 0.0)
    config = SimulationConfig(**config_kwargs)
    pheromone = np.zeros((grid.height, grid.width))
    return AcoPolicy(config, pheromone, distance_map(grid)), pheromone


def _move_shares(policy, grid: Grid, agents: list[Agent], pos=START) -> dict:
    rng = np.random.default_rng(0)
    agent = Agent(id=0, pos=pos)
    counts = Counter(policy.choose_move(agent, grid, rng, agents) for _ in range(SAMPLES))
    return {cell: count / SAMPLES for cell, count in counts.items()}


def test_crowded_direction_loses_its_trail():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher((7, 7)), _searcher((9, 9))])
    assert shares[DIAGONAL] < 0.25  # about 1 of 8: the agent explores instead


def test_agent_picks_the_uncrowded_trail():
    grid = _open_grid()
    grid.add_can((9, 9))  # outside the window of DOWN
    policy, pheromone = _crowd_policy(grid, pheromone_base=1e-6)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    pheromone[DOWN[1], DOWN[0]] = 1.0
    shares = _move_shares(policy, grid, [_searcher((8, 8)), _searcher((10, 10))])
    assert shares[DOWN] > 0.95


def test_penalty_scales_the_trail():
    grid = _open_grid()
    grid.add_can((9, 9))
    policy, pheromone = _crowd_policy(grid, pheromone_base=1e-6, crowd_penalty=0.5)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 2.0
    pheromone[DOWN[1], DOWN[0]] = 1.0
    shares = _move_shares(policy, grid, [_searcher((8, 8)), _searcher((10, 10))])
    assert shares[DIAGONAL] == pytest.approx(0.5, abs=0.04)
    assert shares[DOWN] == pytest.approx(0.5, abs=0.04)


def test_penalty_of_one_turns_crowd_avoidance_off():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy, pheromone = _crowd_policy(grid, crowd_penalty=1.0)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher((7, 7)), _searcher((9, 9))])
    assert shares[DIAGONAL] > 0.95


def test_as_many_agents_as_cans_is_not_a_crowd():
    grid = _open_grid()
    grid.add_can((8, 8), 2)
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher((7, 7)), _searcher((9, 9))])
    assert shares[DIAGONAL] > 0.95


def test_carrying_agents_do_not_make_a_crowd():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    leaving = [
        Agent(id=1, pos=(7, 7), state=AgentState.CARRYING),
        Agent(id=2, pos=(9, 9), state=AgentState.CARRYING),
    ]
    assert _move_shares(policy, grid, leaving)[DIAGONAL] > 0.95


def test_agents_walking_a_trail_away_from_any_cans_are_not_a_crowd():
    grid = _open_grid()
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher((7, 7)), _searcher((9, 9))])
    assert shares[DIAGONAL] > 0.95


def test_crowd_in_another_direction_does_not_matter():
    grid = _open_grid()
    grid.add_can((2, 2))
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher((1, 1)), _searcher((3, 3))])
    assert shares[DIAGONAL] > 0.95


def test_agent_itself_is_not_part_of_the_crowd():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    agent = Agent(id=0, pos=START)
    rng = np.random.default_rng(0)
    others = [agent, _searcher((7, 7))]
    moves = Counter(policy.choose_move(agent, grid, rng, others) for _ in range(SAMPLES))
    assert moves[DIAGONAL] / SAMPLES > 0.95


@pytest.mark.parametrize(
    ("base", "pos", "option", "can", "crowd"),
    [
        ((0, 0), (9, 5), (10, 6), (10, 8), [(10, 7), (10, 9)]),  # window past the right edge
        ((10, 10), (1, 5), (0, 4), (0, 2), [(0, 1), (0, 3)]),  # window past the left edge
    ],
)
def test_crowd_window_is_clipped_at_the_map_edge(base, pos, option, can, crowd):
    grid = _open_grid(base=base)
    grid.add_can(can)
    policy, pheromone = _crowd_policy(grid)
    pheromone[option[1], option[0]] = 10.0
    shares = _move_shares(policy, grid, [_searcher(cell) for cell in crowd], pos=pos)
    assert shares.get(option, 0.0) < 0.25


def test_policy_without_other_agents_sees_no_crowd():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy, pheromone = _crowd_policy(grid)
    pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
    agent = Agent(id=0, pos=START)
    assert policy.choose_move(agent, grid, np.random.default_rng(0)) == DIAGONAL


def test_simulation_shows_the_policy_where_the_agents_are():
    moved_along_trail = 0
    for seed in range(100):
        grid = _open_grid()
        grid.add_can((8, 8))
        config = SimulationConfig(
            n_agents=3, exploration_rate=0.0, crowd_radius=2, crowd_penalty=0.0
        )
        pheromone = np.zeros((grid.height, grid.width))
        policy = AcoPolicy(config, pheromone, distance_map(grid))
        sim = Simulation(config, grid, policy, np.random.default_rng(seed), pheromone=pheromone)
        sim.pheromone[DIAGONAL[1], DIAGONAL[0]] = 10.0
        sim.agents[0].pos = START
        sim.agents[1].pos = (7, 7)
        sim.agents[2].pos = (9, 9)
        sim.step()
        moved_along_trail += sim.agents[0].pos == DIAGONAL
    assert moved_along_trail < 25


def test_a_wall_hides_the_crowd_behind_it():
    config = SimulationConfig(crowd_radius=3, crowd_penalty=0.0)
    grid = Grid(30, 11)
    grid.add_obstacle(12, 0, 1, 11)  # splits the window ahead of the agent
    grid.add_can((15, 5))
    pheromone = np.zeros((11, 30))
    policy = AcoPolicy(config, pheromone, np.zeros((11, 30), dtype=np.int32))
    crowd = [Agent(i, (15, 3 + i)) for i in range(3)]  # behind the wall, more agents than cans
    assert not policy._is_crowded((10, 5), (11, 5), grid, crowd)
