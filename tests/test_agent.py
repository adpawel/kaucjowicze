import numpy as np

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import Simulation


def _single_agent_sim(grid: Grid, **config_kwargs) -> Simulation:
    config = SimulationConfig(n_agents=1, seed=0, **config_kwargs)
    policy = RandomWalkPolicy(config.direction_persistence)
    return Simulation(config, grid, policy, np.random.default_rng(0))


def test_new_agent_is_searching_with_empty_bag():
    agent = Agent(id=0, pos=(1, 2))
    assert agent.state is AgentState.SEARCHING
    assert agent.bag == 0
    assert agent.cans_collected == 0
    assert agent.path_length == 0
    assert agent.trips == 0


def test_carrying_agent_returns_by_shortest_path_and_deposits():
    grid = Grid(10, 10)
    grid.add_base((0, 0))
    sim = _single_agent_sim(grid)
    agent = sim.agents[0]
    agent.pos = (6, 3)
    agent.bag = 4
    agent.state = AgentState.CARRYING

    for _ in range(5):
        sim.step()
    assert agent.state is AgentState.CARRYING
    assert agent.bag == 4

    sim.step()  # sixth step reaches the base (Chebyshev distance 6)
    assert agent.pos == (0, 0)
    assert agent.state is AgentState.SEARCHING
    assert agent.bag == 0
    assert agent.cans_collected == 4
    assert agent.trips == 1
    assert agent.path_length == 6
    assert sim.collected == 4


def test_agent_picks_one_can_per_step_and_returns_when_bag_full():
    grid = Grid(10, 10)
    grid.add_base((0, 0))
    grid.add_can((5, 5), 12)
    sim = _single_agent_sim(grid, bag_capacity=10)
    agent = sim.agents[0]
    agent.pos = (5, 5)

    sim.step()
    assert agent.bag == 1
    assert agent.pos == (5, 5)

    for _ in range(9):
        sim.step()
    assert agent.bag == 10
    assert agent.state is AgentState.CARRYING
    assert grid.cans[5, 5] == 2


def test_agent_walks_to_visible_can():
    grid = Grid(10, 10)
    grid.add_base((0, 0))
    grid.add_can((7, 5))
    sim = _single_agent_sim(grid, vision_radius=2)
    agent = sim.agents[0]
    agent.pos = (5, 5)

    sim.step()
    assert agent.pos == (6, 5)
    sim.step()
    assert agent.pos == (7, 5)
    sim.step()
    assert agent.bag == 1
    assert grid.total_cans == 0


def test_agent_with_cans_returns_after_patience_runs_out():
    grid = Grid(30, 30)
    grid.add_base((0, 0))
    sim = _single_agent_sim(grid, return_patience=5)
    agent = sim.agents[0]
    agent.pos = (15, 15)
    agent.bag = 3

    for _ in range(4):
        sim.step()
    assert agent.state is AgentState.SEARCHING
    sim.step()
    assert agent.state is AgentState.CARRYING


def test_agent_with_empty_bag_keeps_searching():
    grid = Grid(30, 30)
    grid.add_base((0, 0))
    sim = _single_agent_sim(grid, return_patience=5)
    agent = sim.agents[0]
    agent.pos = (15, 15)

    for _ in range(20):
        sim.step()
    assert agent.state is AgentState.SEARCHING


def test_random_walk_stays_in_place_when_boxed_in():
    grid = Grid(3, 3)
    grid.add_obstacle(0, 0, 3, 3)
    grid.obstacles[1, 1] = False
    agent = Agent(id=0, pos=(1, 1))
    policy = RandomWalkPolicy(persistence=0.5)
    assert policy.choose_move(agent, grid, np.random.default_rng(0)) == (1, 1)


def test_random_walk_keeps_heading_with_full_persistence():
    grid = Grid(10, 10)
    agent = Agent(id=0, pos=(2, 5), heading=(1, 0))
    policy = RandomWalkPolicy(persistence=1.0)
    rng = np.random.default_rng(0)
    for expected_x in range(3, 8):
        agent.pos = policy.choose_move(agent, grid, rng)
        assert agent.pos == (expected_x, 5)
