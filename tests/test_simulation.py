import numpy as np

from kaucjowicze.agent import AgentState
from kaucjowicze.cans import scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.maps import build_test_map
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import Simulation


def _test_map_sim(seed: int, **config_kwargs) -> Simulation:
    config = SimulationConfig(seed=seed, **config_kwargs)
    rng = np.random.default_rng(seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, rng)
    return Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)


def test_agents_start_at_base():
    sim = _test_map_sim(seed=0)
    assert len(sim.agents) == sim.config.n_agents
    assert all(agent.pos == sim.grid.bases[0] for agent in sim.agents)
    assert sim.step_count == 0
    assert sim.collected == 0


def test_simulation_without_aco_has_no_pheromone():
    assert _test_map_sim(seed=0).pheromone is None


def test_agents_never_leave_free_cells():
    sim = _test_map_sim(seed=1, max_steps=500)
    for _ in range(500):
        sim.step()
        for agent in sim.agents:
            assert sim.grid.is_free(agent.pos)


def test_cans_are_conserved():
    sim = _test_map_sim(seed=2, max_steps=500)
    initial = sim.initial_cans
    for _ in range(500):
        sim.step()
        in_bags = sum(agent.bag for agent in sim.agents)
        assert sim.grid.total_cans + in_bags + sim.collected == initial
        assert sim.collected == sum(agent.cans_collected for agent in sim.agents)
        assert all(0 <= agent.bag <= sim.config.bag_capacity for agent in sim.agents)


def test_same_seed_gives_same_run():
    a = _test_map_sim(seed=7, max_steps=300)
    b = _test_map_sim(seed=7, max_steps=300)
    a.run()
    b.run()
    assert a.collected == b.collected
    assert [ag.pos for ag in a.agents] == [ag.pos for ag in b.agents]
    assert [ag.cans_collected for ag in a.agents] == [ag.cans_collected for ag in b.agents]


def test_run_stops_at_max_steps():
    sim = _test_map_sim(seed=3, max_steps=50)
    sim.run()
    assert sim.step_count == 50
    assert sim.is_finished


def test_small_map_is_fully_collected():
    grid = Grid(15, 15)
    grid.add_obstacle(4, 4, 3, 3)
    grid.add_base((7, 7))
    rng = np.random.default_rng(5)
    free = grid.free_cells()
    for idx in rng.choice(len(free), size=20, replace=True):
        grid.add_can((int(free[idx][0]), int(free[idx][1])))
    config = SimulationConfig(n_agents=3, bag_capacity=5, max_steps=3000, seed=5)
    sim = Simulation(config, grid, RandomWalkPolicy(config.direction_persistence), rng)

    sim.run()

    assert sim.collected == 20
    assert grid.total_cans == 0
    assert sim.step_count < config.max_steps
    assert sim.is_finished
    assert all(agent.bag == 0 for agent in sim.agents)
    assert sum(agent.trips for agent in sim.agents) >= 20 // config.bag_capacity


def test_agents_make_progress_on_test_map():
    sim = _test_map_sim(seed=0, max_steps=1000)
    sim.run()
    assert sim.collected > 0
    assert any(agent.trips > 0 for agent in sim.agents)
    assert any(agent.state is AgentState.SEARCHING for agent in sim.agents)
