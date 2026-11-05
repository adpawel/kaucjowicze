from collections import Counter

import numpy as np
import pytest

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.maps import build_test_map
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import AcoPolicy, RandomWalkPolicy
from kaucjowicze.simulation import Simulation

SAMPLES = 2000

# On an open grid with the base at (0, 0) the distance to base is max(x, y), so from (5, 5):
START = (5, 5)
OUTWARD_A, OUTWARD_B = (6, 6), (5, 6)  # distance 6: away from the base
LATERAL = (4, 5)  # distance 5: neither closer nor farther
INWARD = (4, 4)  # distance 4: back towards the base


def _open_grid(size: int = 11) -> Grid:
    grid = Grid(size, size)
    grid.add_base((0, 0))
    return grid


def _policy(grid: Grid, **config_kwargs) -> tuple[AcoPolicy, np.ndarray]:
    config_kwargs.setdefault("exploration_rate", 0.0)
    config = SimulationConfig(**config_kwargs)
    pheromone = np.zeros((grid.height, grid.width))
    return AcoPolicy(config, pheromone, distance_map(grid)), pheromone


def _move_shares(policy: AcoPolicy, grid: Grid, agent: Agent) -> dict:
    rng = np.random.default_rng(0)
    counts = Counter(policy.choose_move(agent, grid, rng) for _ in range(SAMPLES))
    return {cell: count / SAMPLES for cell, count in counts.items()}


def _aco_sim(grid: Grid, config: SimulationConfig, rng: np.random.Generator) -> Simulation:
    pheromone = np.zeros((grid.height, grid.width))
    policy = AcoPolicy(config, pheromone, distance_map(grid))
    return Simulation(config, grid, policy, rng, pheromone=pheromone)


def _aco_test_map_sim(seed: int, **config_kwargs) -> Simulation:
    config = SimulationConfig(seed=seed, **config_kwargs)
    rng = np.random.default_rng(seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    return _aco_sim(grid, config, rng)


def test_agent_follows_strong_trail_away_from_base():
    grid = _open_grid()
    policy, pheromone = _policy(grid)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 10.0
    assert _move_shares(policy, grid, Agent(id=0, pos=START))[OUTWARD_A] > 0.95


@pytest.mark.parametrize("cell", [INWARD, LATERAL])
def test_trail_not_leading_away_from_base_does_not_attract(cell):
    grid = _open_grid()
    policy, pheromone = _policy(grid)
    pheromone[cell[1], cell[0]] = 10.0
    assert _move_shares(policy, grid, Agent(id=0, pos=START))[cell] < 0.25  # about 1 of 8


def test_agent_on_trail_goes_outward_not_back():
    grid = _open_grid()
    policy, pheromone = _policy(grid)
    pheromone[INWARD[1], INWARD[0]] = 10.0
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 10.0
    assert _move_shares(policy, grid, Agent(id=0, pos=START))[OUTWARD_A] > 0.95


def test_choice_is_proportional_to_trail_strength():
    grid = _open_grid()
    policy, pheromone = _policy(grid, pheromone_base=1e-6)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 3.0
    pheromone[OUTWARD_B[1], OUTWARD_B[0]] = 1.0
    shares = _move_shares(policy, grid, Agent(id=0, pos=START))
    assert shares[OUTWARD_A] == pytest.approx(0.75, abs=0.04)
    assert shares[OUTWARD_B] == pytest.approx(0.25, abs=0.04)


def test_alpha_sharpens_the_choice():
    grid = _open_grid()
    policy, pheromone = _policy(grid, pheromone_base=1e-6, pheromone_alpha=2.0)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 3.0
    pheromone[OUTWARD_B[1], OUTWARD_B[0]] = 1.0
    shares = _move_shares(policy, grid, Agent(id=0, pos=START))
    assert shares[OUTWARD_A] == pytest.approx(0.9, abs=0.04)


def test_base_level_lets_agent_leave_a_weak_trail():
    grid = _open_grid()
    policy, pheromone = _policy(grid, pheromone_base=0.1)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 0.3  # weight 0.4 against 0.1 for 7 other neighbours
    shares = _move_shares(policy, grid, Agent(id=0, pos=START))
    assert shares[OUTWARD_A] == pytest.approx(0.4 / 1.1, abs=0.04)


def test_exploration_ignores_the_trail():
    grid = _open_grid()
    policy, pheromone = _policy(grid, exploration_rate=1.0)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 1000.0
    shares = _move_shares(policy, grid, Agent(id=0, pos=START, heading=(1, 1)))
    assert len(shares) == 8
    assert shares[OUTWARD_A] < 0.25


def test_without_trail_agent_explores_like_the_random_walk():
    grid = _open_grid()
    policy, _ = _policy(grid, direction_persistence=1.0)
    agent = Agent(id=0, pos=(2, 5), heading=(1, 0))
    rng = np.random.default_rng(0)
    for expected_x in range(3, 8):
        agent.pos = policy.choose_move(agent, grid, rng)
        assert agent.pos == (expected_x, 5)


def test_exploration_rate_does_not_change_the_walk_without_a_trail():
    grid = _open_grid()
    policy, _ = _policy(grid, direction_persistence=1.0, exploration_rate=1.0)
    agent = Agent(id=0, pos=(2, 5), heading=(1, 0))
    rng = np.random.default_rng(0)
    for expected_x in range(3, 8):
        agent.pos = policy.choose_move(agent, grid, rng)
        assert agent.pos == (expected_x, 5)


def test_trail_fainter_than_base_level_is_ignored():
    grid = _open_grid()
    policy, pheromone = _policy(grid, direction_persistence=1.0, pheromone_base=0.01)
    pheromone[OUTWARD_A[1], OUTWARD_A[0]] = 0.005
    agent = Agent(id=0, pos=START, heading=(1, 0))
    assert policy.choose_move(agent, grid, np.random.default_rng(0)) == (6, 5)


def test_agent_stays_in_place_when_boxed_in():
    grid = Grid(3, 3)
    grid.add_obstacle(0, 0, 3, 3)
    grid.obstacles[1, 1] = False
    grid.add_base((1, 1))
    policy, _ = _policy(grid)
    assert policy.choose_move(Agent(id=0, pos=(1, 1)), grid, np.random.default_rng(0)) == (1, 1)


def test_searching_agent_walks_up_the_trail_to_the_source():
    grid = Grid(30, 30)
    grid.add_base((0, 0))
    grid.add_can((15, 0), 5)
    config = SimulationConfig(
        n_agents=1, exploration_rate=0.0, evaporation_rate=0.0, pheromone_base=1e-6
    )
    sim = _aco_sim(grid, config, np.random.default_rng(0))
    sim.pheromone[0, 1:14] = 5.0

    for _ in range(15):
        sim.step()

    assert sim.agents[0].pos == (15, 0)


def test_agent_comes_back_to_a_rich_source_along_its_own_trail():
    """End to end: pick up, walk home laying a trail, deposit, then follow the trail out."""
    grid = Grid(40, 40)
    grid.add_base((0, 0))
    grid.add_can((30, 0), 40)
    config = SimulationConfig(
        n_agents=1, bag_capacity=5, exploration_rate=0.0, evaporation_rate=0.0, pheromone_base=1e-6
    )
    sim = _aco_sim(grid, config, np.random.default_rng(0))
    agent = sim.agents[0]
    agent.pos = (30, 0)

    for _ in range(35):  # 5 pick-ups and 30 moves
        sim.step()
    assert agent.pos == (0, 0)
    assert agent.state is AgentState.SEARCHING
    assert agent.cans_collected == 5
    assert sim.pheromone[0, 1:31].min() > 0

    for _ in range(30):
        sim.step()
    assert agent.pos == (30, 0)


def test_pheromone_stays_on_free_cells_and_non_negative():
    sim = _aco_test_map_sim(seed=1, max_steps=600)
    sim.run()
    assert sim.pheromone.max() > 0
    assert sim.pheromone.min() >= 0
    assert sim.pheromone[sim.grid.obstacles].sum() == 0


def test_agents_never_leave_free_cells_and_cans_are_conserved():
    sim = _aco_test_map_sim(seed=2)
    initial = sim.initial_cans
    for _ in range(500):
        sim.step()
        assert all(sim.grid.is_free(agent.pos) for agent in sim.agents)
        in_bags = sum(agent.bag for agent in sim.agents)
        assert sim.grid.total_cans + in_bags + sim.collected == initial
        assert sim.collected == sum(agent.cans_collected for agent in sim.agents)


def test_same_seed_gives_same_run():
    a = _aco_test_map_sim(seed=7, max_steps=300)
    b = _aco_test_map_sim(seed=7, max_steps=300)
    a.run()
    b.run()
    assert a.collected == b.collected
    assert [agent.pos for agent in a.agents] == [agent.pos for agent in b.agents]
    assert (a.pheromone == b.pheromone).all()


def test_trails_fade_once_nobody_lays_them():
    sim = _aco_test_map_sim(seed=3, max_steps=300)
    sim.run()
    assert sim.pheromone.max() > 0
    peak = sim.pheromone.max()
    sim.grid.cans[:] = 0  # nothing left to find, so no agent can report a rich source
    for agent in sim.agents:
        agent.source_cans = 0
    for _ in range(300):
        sim.step()
    assert sim.pheromone.max() < peak * 0.01


def test_aco_collects_more_than_random_walk_on_the_same_maps():
    seeds = range(6)
    aco = random = 0
    for seed in seeds:
        sim = _aco_test_map_sim(seed, max_steps=600)
        sim.run()
        aco += sim.collected

        config = SimulationConfig(seed=seed, max_steps=600)
        rng = np.random.default_rng(seed)
        grid = build_test_map(config)
        scatter_cans(grid, config, rng)
        baseline = Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)
        baseline.run()
        random += baseline.collected
    assert aco > random
