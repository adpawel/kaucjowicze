import numpy as np
import pytest

from kaucjowicze.agent import AgentState
from kaucjowicze.cans import SpawnEvent, scatter_cans
from kaucjowicze.config import SimulationConfig
from kaucjowicze.factory import build_simulation
from kaucjowicze.grid import Grid
from kaucjowicze.maps import build_test_map
from kaucjowicze.policies import RandomWalkPolicy
from kaucjowicze.simulation import CanLedger, Simulation


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


def _corridor_with_party(step: int, cans: int = 2, max_steps: int = 50) -> Simulation:
    """One agent, a corridor without cans and a party two cells from the base at `step`."""
    grid = Grid(5, 1)
    grid.add_base((0, 0))
    config = SimulationConfig(
        width=5, height=1, n_agents=1, bag_capacity=2, max_steps=max_steps, seed=0
    )
    event = SpawnEvent(1, step, (2, 0), ((2, 0),) * cans)
    rng = np.random.default_rng(0)
    policy = RandomWalkPolicy(config.direction_persistence)
    return Simulation(config, grid, policy, rng, events=[event])


def test_party_cans_appear_exactly_at_their_step():
    sim = _corridor_with_party(step=3)
    assert sim.grid.total_cans == 0
    assert sim.total_cans == 2
    for _ in range(2):
        sim.step()
        assert sim.grid.total_cans == 0
    sim.step()
    assert sim.step_count == 3
    assert sim.grid.cans[0, 2] == 2
    assert sim.events_spawned == 1
    assert sim.next_event is None


def test_party_at_step_zero_is_there_from_the_start():
    sim = _corridor_with_party(step=0)
    assert sim.grid.total_cans == 2
    assert sim.initial_cans == 0


def test_run_does_not_end_before_the_last_party():
    sim = _corridor_with_party(step=20)
    assert not sim.is_finished  # nothing to collect yet, but the party is still to come
    sim.run()
    assert sim.collected == 2
    assert sim.step_count > 20


def test_party_ids_must_follow_their_order():
    grid = Grid(5, 1)
    grid.add_base((0, 0))
    config = SimulationConfig(width=5, height=1, n_agents=1, max_steps=10)
    events = [SpawnEvent(2, 1, (2, 0), ((2, 0),)), SpawnEvent(1, 5, (3, 0), ((3, 0),))]
    with pytest.raises(ValueError, match="ids"):
        Simulation(config, grid, RandomWalkPolicy(0.5), np.random.default_rng(0), events=events)


@pytest.mark.parametrize(
    ("algorithm", "reward"), [("random", None), ("aco", "shared"), ("aco", "individual")]
)
def test_cans_are_conserved_with_parties(algorithm, reward):
    config = SimulationConfig(scenario="dynamic", event_start=50, event_interval=50, max_steps=400)
    sim = build_simulation(algorithm, seed=2, reward=reward, config=config)
    for _ in range(400):
        sim.step()
        spawned = sim.initial_cans + sum(e.cans for e in sim.events[: sim.events_spawned])
        in_bags = sum(agent.bag for agent in sim.agents)
        assert sim.grid.total_cans + in_bags + sim.collected == spawned
        assert (sim.ledger.counts.sum(axis=0) == sim.grid.cans).all()


def test_ledger_takes_the_oldest_can_on_a_cell():
    grid = Grid(3, 1)
    grid.add_can((1, 0))
    ledger = CanLedger(grid, n_events=2)
    ledger.add(2, (1, 0))
    ledger.add(1, (1, 0))
    assert [ledger.take((1, 0)) for _ in range(4)] == [0, 1, 2, None]
