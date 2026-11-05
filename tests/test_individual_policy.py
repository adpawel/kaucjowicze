import numpy as np

from kaucjowicze.agent import Agent
from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.maps import build_test_map
from kaucjowicze.pathfinding import distance_map
from kaucjowicze.policies import IndividualPolicy
from kaucjowicze.simulation import Simulation

START = (5, 5)
DIAGONAL = (6, 6)


def _searcher(pos: tuple[int, int], agent_id: int = 1) -> Agent:
    return Agent(id=agent_id, pos=pos)


def _open_grid(size: int = 11, base: tuple[int, int] = (0, 0)) -> Grid:
    grid = Grid(size, size)
    grid.add_base(base)
    return grid


def _individual_sim(grid: Grid, **config_kwargs) -> Simulation:
    config_kwargs.setdefault("n_agents", 1)
    config = SimulationConfig(seed=0, **config_kwargs)
    return Simulation(config, grid, IndividualPolicy(config), np.random.default_rng(0))


def _individual_test_map_sim(seed: int, **config_kwargs) -> Simulation:
    config = SimulationConfig(seed=seed, **config_kwargs)
    rng = np.random.default_rng(seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    return Simulation(config, grid, IndividualPolicy(config), rng)


def test_pickup_remembers_the_source():
    grid = _open_grid(20)
    grid.add_can((10, 10), 6)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (10, 10)

    sim.step()

    assert agent.remembered_source == (10, 10)
    assert agent.remembered_cans == 5


def test_poorer_pickup_elsewhere_keeps_the_memory():
    grid = _open_grid(20)
    grid.add_can((5, 5), 3)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (5, 5)
    agent.remembered_source = (15, 15)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source == (15, 15)
    assert agent.remembered_cans == 8


def test_richer_pickup_elsewhere_replaces_the_memory():
    grid = _open_grid(20)
    grid.add_can((5, 5), 10)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (5, 5)
    agent.remembered_source = (15, 15)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source == (5, 5)
    assert agent.remembered_cans == 9


def test_pickup_at_the_remembered_place_updates_the_stale_count():
    grid = _open_grid(20)
    grid.add_can((6, 6), 3)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (6, 6)
    agent.remembered_source = (5, 5)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source == (6, 6)
    assert agent.remembered_cans == 2


def test_taking_the_last_can_at_the_remembered_place_clears_the_memory():
    grid = _open_grid(20)
    grid.add_can((6, 6))
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (6, 6)
    agent.remembered_source = (5, 5)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source is None
    assert agent.remembered_cans == 0


def test_taking_a_lone_can_elsewhere_keeps_the_memory():
    grid = _open_grid(20)
    grid.add_can((5, 5))
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (5, 5)
    agent.remembered_source = (15, 15)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source == (15, 15)


def test_lone_can_without_memory_is_not_remembered():
    grid = _open_grid(20)
    grid.add_can((5, 5))
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (5, 5)

    sim.step()

    assert agent.remembered_source is None


def test_agent_walks_to_the_remembered_source_by_the_shortest_path():
    grid = Grid(12, 12)
    grid.add_base((0, 0))
    grid.add_obstacle(5, 0, 1, 8)  # a wall between the base and the source
    source = (10, 0)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.remembered_source = source
    agent.remembered_cans = 8
    remaining = distance_map(grid, [source])

    expected_steps = int(remaining[0, 0])
    assert expected_steps > 10  # the straight line is blocked
    for steps_left in range(expected_steps - 1, -1, -1):
        sim.step()
        assert remaining[agent.pos[1], agent.pos[0]] == steps_left
    assert agent.pos == source
    assert agent.remembered_source == source


def test_empty_source_is_forgotten_on_arrival_and_the_agent_explores():
    grid = _open_grid(20)
    sim = _individual_sim(grid)
    agent = sim.agents[0]
    agent.pos = (10, 10)
    agent.remembered_source = (10, 10)
    agent.remembered_cans = 8

    sim.step()

    assert agent.remembered_source is None
    assert agent.remembered_cans == 0
    assert agent.pos != (10, 10)


def test_without_memory_agent_explores_like_the_random_walk():
    grid = _open_grid()
    policy = IndividualPolicy(SimulationConfig(direction_persistence=1.0))
    agent = Agent(id=0, pos=(2, 5), heading=(1, 0))
    rng = np.random.default_rng(0)
    for expected_x in range(3, 8):
        agent.pos = policy.choose_move(agent, grid, rng)
        assert agent.pos == (expected_x, 5)


def test_egoist_goes_to_its_source_despite_the_crowd():
    grid = _open_grid()
    grid.add_can((8, 8))
    policy = IndividualPolicy(SimulationConfig(crowd_radius=2, crowd_penalty=0.0))
    agent = Agent(id=0, pos=START, remembered_source=(8, 8), remembered_cans=1)
    crowd = [_searcher((7, 7)), _searcher((9, 9))]
    assert policy.choose_move(agent, grid, np.random.default_rng(0), crowd) == DIAGONAL


def test_agent_keeps_coming_back_until_the_source_is_exhausted():
    grid = Grid(40, 40)
    grid.add_base((0, 0))
    grid.add_can((30, 0), 40)
    sim = _individual_sim(grid, bag_capacity=5)
    agent = sim.agents[0]
    agent.pos = (30, 0)

    sim.run()

    assert sim.collected == 40
    assert agent.trips == 8
    assert sim.step_count == 8 * (5 + 30) + 7 * 30  # no step wasted on searching
    assert agent.remembered_source is None


def test_individual_agents_never_leave_free_cells_and_cans_are_conserved():
    sim = _individual_test_map_sim(seed=2)
    initial = sim.initial_cans
    for _ in range(500):
        sim.step()
        assert all(sim.grid.is_free(agent.pos) for agent in sim.agents)
        in_bags = sum(agent.bag for agent in sim.agents)
        assert sim.grid.total_cans + in_bags + sim.collected == initial
        assert sim.collected == sum(agent.cans_collected for agent in sim.agents)


def test_individual_same_seed_gives_same_run():
    a = _individual_test_map_sim(seed=7, max_steps=300)
    b = _individual_test_map_sim(seed=7, max_steps=300)
    a.run()
    b.run()
    assert a.collected == b.collected
    assert [agent.pos for agent in a.agents] == [agent.pos for agent in b.agents]
