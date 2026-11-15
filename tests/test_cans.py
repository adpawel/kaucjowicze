import hashlib

import numpy as np
import pytest

from kaucjowicze.cans import _cluster_candidates, scatter_cans, schedule_events
from kaucjowicze.config import SimulationConfig
from kaucjowicze.grid import Grid
from kaucjowicze.maps import build_map, build_test_map


def _generate(seed: int):
    config = SimulationConfig(seed=seed)
    grid = build_test_map(config)
    scatter_cans(grid, config, np.random.default_rng(seed))
    return config, grid


def test_total_can_count():
    config, grid = _generate(seed=1)
    expected = config.n_clusters * config.cans_per_cluster + config.n_background_cans
    assert grid.total_cans == expected


def test_no_cans_on_obstacles():
    _, grid = _generate(seed=2)
    assert grid.cans[grid.obstacles].sum() == 0


def test_same_seed_gives_same_map():
    _, a = _generate(seed=42)
    _, b = _generate(seed=42)
    np.testing.assert_array_equal(a.cans, b.cans)


def test_test_map_has_reachable_base():
    _, grid = _generate(seed=3)
    assert len(grid.bases) == 1
    assert grid.is_free(grid.bases[0])


def test_invalid_config_rejected():
    with pytest.raises(ValueError):
        SimulationConfig(bag_capacity=0)


def _grid_with_dormitory() -> Grid:
    grid = Grid(60, 40)
    grid.add_obstacle(5, 5, 4, 4)
    grid.dormitories[5:9, 5:9] = True
    return grid


def test_cluster_centres_lie_close_to_a_dormitory():
    grid = _grid_with_dormitory()
    config = SimulationConfig(cluster_dorm_distance=4)
    candidates = _cluster_candidates(grid, config, grid.free_cells())
    assert len(candidates) > 0
    assert candidates[:, 0].min() >= 1 and candidates[:, 0].max() <= 12
    assert candidates[:, 1].min() >= 1 and candidates[:, 1].max() <= 12
    assert not grid.obstacles[candidates[:, 1], candidates[:, 0]].any()


def test_without_dormitories_any_free_cell_can_be_a_centre():
    grid = Grid(10, 10)
    grid.add_obstacle(2, 2, 2, 2)
    free = grid.free_cells()
    assert (_cluster_candidates(grid, SimulationConfig(), free) == free).all()


def test_cans_gather_around_the_dormitory():
    grid = _grid_with_dormitory()
    config = SimulationConfig(
        n_clusters=3, cans_per_cluster=30, cluster_spread=1.0, n_background_cans=0
    )
    scatter_cans(grid, config, np.random.default_rng(0))
    assert grid.total_cans == 90
    assert grid.cans[:, 25:].sum() == 0
    assert not grid.cans[grid.obstacles].any()


def test_no_free_cell_near_a_dormitory_is_an_error_and_does_not_lift_the_constraint():
    grid = Grid(20, 20)
    grid.add_obstacle(0, 0, 8, 8)
    grid.dormitories[0:2, 0:2] = True  # surrounded by other obstacles
    config = SimulationConfig(cluster_dorm_distance=2)
    with pytest.raises(ValueError, match="No free cell within 2 cells"):
        _cluster_candidates(grid, config, grid.free_cells())


@pytest.mark.parametrize(
    ("map_name", "digest"), [("test", "b2006c42003dabcd"), ("campus", "323c04e3cac92fbe")]
)
def test_static_layout_is_unchanged_by_the_parties(map_name, digest):
    # Digests of the layout before parties existed: the static results must not move
    config = SimulationConfig(map_name=map_name, seed=7)
    grid = build_map(config)
    scatter_cans(grid, config, np.random.default_rng(7))
    assert hashlib.sha256(grid.cans.tobytes()).hexdigest()[:16] == digest


def _parties(seed: int, **kwargs):
    config = SimulationConfig(scenario="dynamic", seed=seed, **kwargs)
    grid = build_test_map(config)
    return config, grid, schedule_events(grid, config, np.random.default_rng(seed))


def test_static_scenario_has_no_parties():
    config = SimulationConfig(seed=0)
    grid = build_test_map(config)
    assert schedule_events(grid, config, np.random.default_rng(0)) == []


def test_parties_follow_the_schedule():
    config, grid, events = _parties(seed=0, event_start=100, event_interval=40)
    assert [event.id for event in events] == [1, 2, 3]
    assert [event.step for event in events] == [100, 140, 180]
    for event in events:
        assert event.cans == config.cans_per_event == config.cans_per_cluster
        assert all(grid.is_free(pos) for pos in event.cells)


def test_party_centres_lie_close_to_a_dormitory():
    config, grid, events = _parties(seed=1)
    candidates = {tuple(cell) for cell in _cluster_candidates(grid, config, grid.free_cells())}
    assert all(event.center in candidates for event in events)


def test_same_seed_gives_same_parties():
    assert _parties(seed=5)[2] == _parties(seed=5)[2]
    assert _parties(seed=5)[2] != _parties(seed=6)[2]


def test_cans_per_party_can_differ_from_a_cluster():
    _, _, events = _parties(seed=0, cans_per_event=7)
    assert [event.cans for event in events] == [7, 7, 7]
