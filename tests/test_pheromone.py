import numpy as np
import pytest

from kaucjowicze.agent import Agent, AgentState
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid, Position
from kaucjowicze.pathfinding import visible_cans
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import Simulation


def _trail_sim(grid: Grid, **config_kwargs) -> Simulation:
    config = SimulationConfig(n_agents=1, seed=0, **config_kwargs)
    policy = RandomWalkPolicy(config.direction_persistence)
    pheromone = np.zeros((grid.height, grid.width))
    return Simulation(config, grid, policy, np.random.default_rng(0), pheromone=pheromone)


def _corridor_with_base(width: int = 10) -> Grid:
    grid = Grid(width, 1)
    grid.add_base((0, 0))
    return grid


def _carrying_at(sim: Simulation, pos: Position, source_cans: int) -> Agent:
    agent = sim.agents[0]
    agent.pos = pos
    agent.bag = 5
    agent.state = AgentState.CARRYING
    agent.source_cans = source_cans
    return agent


def test_visible_cans_counts_the_window_around_the_agent():
    grid = Grid(10, 10)
    grid.add_can((5, 5), 3)
    grid.add_can((7, 7), 2)  # corner of the window
    grid.add_can((8, 5), 4)  # just outside
    assert visible_cans(grid, (5, 5), radius=2) == 5
    assert visible_cans(grid, (5, 5), radius=3) == 9
    assert visible_cans(grid, (0, 0), radius=2) == 0


def test_carrying_agent_marks_the_cells_it_leaves():
    sim = _trail_sim(_corridor_with_base(), evaporation_rate=0.0, trail_deposit=0.5)
    _carrying_at(sim, (3, 0), source_cans=4)

    sim.step()
    assert sim.pheromone[0, 3] == pytest.approx(2.0)  # q * cans left at the source
    assert sim.pheromone[0, 2] == 0.0

    sim.step()
    sim.step()  # third step reaches the base, which itself stays unmarked
    expected = [0.0, 2.0, 2.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert sim.pheromone[0].tolist() == pytest.approx(expected)


def test_trail_from_exhausted_source_is_not_left():
    sim = _trail_sim(_corridor_with_base())
    _carrying_at(sim, (3, 0), source_cans=0)
    for _ in range(3):
        sim.step()
    assert sim.pheromone.sum() == 0.0


def test_searching_agent_leaves_no_trail():
    grid = Grid(20, 20)
    grid.add_base((0, 0))
    sim = _trail_sim(grid)
    for _ in range(30):
        sim.step()
    assert sim.pheromone.sum() == 0.0


def test_pickup_remembers_cans_left_around_the_source():
    grid = Grid(10, 10)
    grid.add_base((0, 0))
    grid.add_can((5, 5), 3)
    grid.add_can((6, 6), 2)  # visible from the source
    grid.add_can((9, 9), 7)  # too far to be seen
    sim = _trail_sim(grid, vision_radius=2)
    agent = sim.agents[0]
    agent.pos = (5, 5)

    sim.step()

    assert agent.bag == 1
    assert agent.source_cans == 4  # 2 left on the cell + 2 next to it


def test_agent_taking_the_last_can_leaves_no_trail_home():
    grid = _corridor_with_base()
    grid.add_can((4, 0))
    sim = _trail_sim(grid, bag_capacity=1)
    agent = sim.agents[0]
    agent.pos = (4, 0)

    sim.step()
    assert agent.state is AgentState.CARRYING
    for _ in range(4):
        sim.step()

    assert agent.cans_collected == 1
    assert sim.pheromone.sum() == 0.0


def test_full_bag_from_rich_source_lays_trail_home():
    grid = _corridor_with_base()
    grid.add_can((4, 0), 6)
    sim = _trail_sim(grid, bag_capacity=1, evaporation_rate=0.0, trail_deposit=1.0)
    sim.agents[0].pos = (4, 0)

    for _ in range(5):
        sim.step()

    assert sim.agents[0].cans_collected == 1
    expected = [0.0, 5.0, 5.0, 5.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert sim.pheromone[0].tolist() == pytest.approx(expected)


def test_deposit_clears_remembered_source():
    sim = _trail_sim(_corridor_with_base())
    agent = _carrying_at(sim, (1, 0), source_cans=4)
    sim.step()
    assert agent.state is AgentState.SEARCHING
    assert agent.source_cans == 0


def test_pheromone_evaporates_every_step():
    grid = Grid(20, 20)
    grid.add_base((0, 0))
    sim = _trail_sim(grid, evaporation_rate=0.1)
    sim.pheromone[10, 10] = 1.0

    sim.step()
    assert sim.pheromone[10, 10] == pytest.approx(0.9)

    for _ in range(9):
        sim.step()
    assert sim.pheromone[10, 10] == pytest.approx(0.9**10)


def test_fresh_deposit_evaporates_in_the_same_step():
    sim = _trail_sim(_corridor_with_base(), evaporation_rate=0.5, trail_deposit=1.0)
    _carrying_at(sim, (3, 0), source_cans=4)
    sim.step()
    assert sim.pheromone[0, 3] == pytest.approx(2.0)


def test_pheromone_with_wrong_shape_is_rejected():
    grid = Grid(5, 4)
    grid.add_base((0, 0))
    config = SimulationConfig(n_agents=1)
    policy = RandomWalkPolicy(config.direction_persistence)
    with pytest.raises(ValueError, match="shape"):
        Simulation(config, grid, policy, np.random.default_rng(0), pheromone=np.zeros((5, 4)))
